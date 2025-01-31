##########################################################################
#  (C) Copyright Mojaloop Foundation. 2024 - All rights reserved.        #
#                                                                        #
#  This file is made available under the terms of the license agreement  #
#  specified in the corresponding source code repository.                #
#                                                                        #
#  ORIGINAL AUTHOR:                                                      #
#       James Bush - jbush@mojaloop.io                                   #
#                                                                        #
#  CONTRIBUTORS:                                                         #
#       James Bush - jbush@mojaloop.io                                   #
##########################################################################

import json
import os
import sys
import time
import docker
import hvac

from docker.errors import NotFound
from hvac.exceptions import InvalidRequest
from mcmClient import ConnectionManagerClient


class PkiTools:
    """
    We use hashicorp vault running as a docker container to perform PKI operations.
    Note that hvac is a python client wrapper around the vault HTTP API.

    We use the python docker client to manipulate the vault container.
    """
    vault_container_name = 'itk-configurator-vault'
    vault_root_token = None
    container_start_timeout_secs = 60
    jws_key_type = 'rsa-2048'
    vault_init_file = 'vaultinit.json'
    vault_url = 'http://localhost:8200'
    vault_unseal_key = None
    vault_cert_role_name = 'itk-dfsp-server-role'
    vault_default_cert_ttl = '720h'
    vault_pki_policy = '''
path "sys/mounts/*" {
    capabilities = ["create", "read", "update", "delete", "list"]
}

path "sys/mounts" {
    capabilities = ["read", "list"]
},

path "pki*" {
    capabilities = ["create", "read", "update", "delete", "list", "sudo", "patch"]
}
'''

    def __init__(self):
        # use the local docker install
        self.dockerClient = docker.from_env()

        self.start_vault_container()
        self.vaultClient = hvac.Client(url=self.vault_url)

        if not self.wait_for_vault_container_healthy():
            raise TimeoutError('Vault container did not reach healthy status within timeout of {} seconds'
                               .format(self.container_start_timeout_secs))

        self.initialize_vault()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.seal_vault()
        self.stop_vault_container()

    def start_vault_container(self):
        print('Starting vault container...')
        # does the container exist already?
        try:
            vault_container = self.dockerClient.containers.get(self.vault_container_name)

            if vault_container.status == 'exited':
                # we need to start the container
                vault_container.start()

        except NotFound as e:
            # we need to create the container
            print('Creating vault container...')
            vault_container = self.dockerClient.containers.run(
                name=self.vault_container_name,
                image='hashicorp/vault',
                detach=True,
                cap_add=['IPC_LOCK'],
                environment={
                    'VAULT_LOCAL_CONFIG': '{"storage": {"file": {"path": "/vault/file"}}, "listener": [{"tcp": { "address": "0.0.0.0:8200", "tls_disable": true}}], "default_lease_ttl": "168h", "max_lease_ttl": "720h", "ui": true}',
                },
                command='server',
                ports={
                    '8200/tcp': 8200,
                },
                volumes={
                    os.path.abspath('./vaultfile'): {
                        'bind': '/vault/file',
                        'mode': 'rw'
                    }
                }
            )

    def stop_vault_container(self):
        # does the container exist already?
        print('Stopping vault container...')
        try:
            vault_container = self.dockerClient.containers.get(self.vault_container_name)

            if vault_container.status == 'running':
                # we need to start the container
                vault_container.stop()

        except NotFound as e:
            # nothing to do
            pass

        print('Vault container stopped.')

    def initialize_vault(self):
        # try to init the vault, ignore error if already initialized
        print('Initializing vault...')
        try:
            result = self.vaultClient.sys.initialize(1, 1)

            with open(self.vault_init_file, 'w') as file:
                json.dump(result, file, indent=2)

            self.create_client()
            self.unseal_vault()
            self.enable_vault_pki()
            self.enable_vault_transit()
            return

        except InvalidRequest as e:
            if not str(e).startswith('Vault is already initialized'):
                raise e

        self.create_client()
        self.unseal_vault()

    def unseal_vault(self):
        print('Unsealing vault...')
        if self.vaultClient.sys.is_sealed():
            response = self.vaultClient.sys.submit_unseal_key(key=self.vault_unseal_key)
            if response['sealed']:
                raise Exception('Failed to unseal vault')

    def seal_vault(self):
        print('Sealing vault...')
        if not self.vaultClient.sys.is_sealed():
            self.vaultClient.sys.seal()

    def create_client(self):
        with open(self.vault_init_file, 'r') as file:
            init_data = json.load(file)

        self.vault_unseal_key = init_data['keys'][0]
        self.vault_root_token = init_data['root_token']
        self.vaultClient = hvac.Client(url=self.vault_url, token=self.vault_root_token)

    def wait_for_vault_container_healthy(self):
        print('Waiting for vault container to be healthy...')
        # Check health status in a loop
        start_time = time.time()
        while time.time() - start_time < self.container_start_timeout_secs:
            try:
                # check we can connect to the vault container by trying to read the seal status
                result = self.vaultClient.sys.read_seal_status()
                return True
            except Exception as e:
                # probably an error try to connect meaning the container is not fully healthy yet. try again.
                time.sleep(2)

        # Timeout case
        print('Timeout waiting for vault container to become healthy.')
        return False

    def enable_vault_pki(self):
        print('Enabling vault PKI secrets engine...')
        # add PKI paths to default policy
        current_default_policy = self.vaultClient.sys.read_policy(name='default')['data']['rules']
        updated_policy = '{}\n{}'.format(current_default_policy, self.vault_pki_policy)
        result = self.vaultClient.sys.create_or_update_policy('default', policy=updated_policy)

        # enable PKI secrets engine
        result = self.vaultClient.sys.enable_secrets_engine(backend_type='pki', path='pki', config={
            'default_lease_ttl': '8760h',
            'max_lease_ttl': '87600h'
        })

    def enable_vault_transit(self):
        print('Enabling vault Transit secrets engine...')
        # enable transit secrets engine
        result = self.vaultClient.sys.enable_secrets_engine(backend_type='transit', path='transit', config={
            'default_lease_ttl': '8760h',
            'max_lease_ttl': '87600h'
        })

    def create_cert_role_if_not_exists(self):
        print('Setting certificate issuer role parameters...')
        role_params = {
            'allowed_domains': '*',
            'allow_any_name': True,
            'allow_bare_domains': True,
            'allow_subdomains': True,
            'max_ttl': '4380h'
        }

        result = self.vaultClient.secrets.pki.create_or_update_role(self.vault_cert_role_name, role_params)

    def generate_cert(self, common_name, alt_names=None):
        print('Generating certificate for {}...'.format(common_name))
        cert_params = {
            'ttl': '4380h',
            'private_key_format': 'pem',
        }

        if alt_names is not None:
            cert_params['alt_names'] = alt_names

        return self.vaultClient.secrets.pki.generate_certificate(
            name=self.vault_cert_role_name,
            common_name=common_name,
            extra_params=cert_params,
        )

    def generate_intermediate_cert(self, common_name, alt_names=None):
        print('Generating private key and CSR for {}...'.format(common_name))
        cert_params = {
            'ttl': '4380h',
            'private_key_format': 'pem',
        }

        if alt_names is not None:
            cert_params['alt_names'] = alt_names

        return self.vaultClient.secrets.pki.generate_intermediate(
            type='exported',
            common_name=common_name,
            extra_params=cert_params,
        )


    def create_client_mtls_artefacts(self, dfsp_name, root_ca_cert_path, server_cert_path, server_cert_key_path,
                                     client_cert_path, client_cert_key_path, alt_names):
        print('Generating client mTLS artifacts...')
        # always create a new root CA certificate (issuer)

        # delete any existing issuer
        print('Deleting any existing issuer...')
        try:
            issuers = self.vaultClient.secrets.pki.list_issuers()
            delete_result = self.vaultClient.secrets.pki.delete_issuer(issuers['data']['keys'][0])
        except Exception as e:
            print('Error deleting existing issuer: {}'.format(e))

        # generate a new self-signed root certificate authority
        print('Creating new root CA issuer...')
        result = self.vaultClient.secrets.pki.generate_root(
            type='internal',
            common_name='{} Root CA'.format(dfsp_name),
            extra_params={
                'issuer_name': dfsp_name,
                'key_bits': 4096,
                'organization': dfsp_name,
                'ttl': '8760h'
            }
        )

        # make sure we have created a vault "role" for our server certs
        self.create_cert_role_if_not_exists()

        # write the root CA cert to disk
        root_cert = result['data']['certificate']
        with open(root_ca_cert_path, 'w') as file:
            file.write(root_cert)

        # request a signed server cert
        server_cert_data = self.generate_cert('{}.com'.format(dfsp_name), alt_names=alt_names)
        server_cert = server_cert_data['data']['certificate']
        server_cert_key = server_cert_data['data']['private_key']

        # request a signed client cert
        client_cert_data = self.generate_intermediate_cert('{}.com'.format(dfsp_name), alt_names=alt_names)
        client_cert = client_cert_data['data']['csr']
        client_cert_key = client_cert_data['data']['private_key']

        # write the server cert to disk
        with open(server_cert_path, 'w') as file:
            file.write(server_cert)

        # write the server cert private key to disk
        with open(server_cert_key_path, 'w') as file:
            file.write(server_cert_key)

        # write the client cert to disk
        with open(client_cert_path + '.csr', 'w') as file:
            file.write(client_cert)

        # write the client cert private key to disk
        with open(client_cert_key_path, 'w') as file:
            file.write(client_cert_key)

        print('New client mTLS artifacts successfully generated and written to disk.')

    def create_jws_keypair(self, key_name, private_key_path, public_key_path):
        # Note that creating a key with the same name as an existing key will create
        # a new "version" of the key in vault.

        # create a transit keypair
        print('Creating new JWS keypair...')
        result = self.vaultClient.secrets.transit.create_key(key_name, exportable=True, key_type=self.jws_key_type)
        public_key = result['data']['keys']['1']['public_key']

        # we only get the public key returned so we need to export to get the private key
        result = self.vaultClient.secrets.transit.export_key(key_name, 'signing-key')
        private_key = result['data']['keys']['1']

        # write the keys to disk
        print('Writing keys to disk...')

        with open(public_key_path, 'w') as file:
            file.write(public_key)

        with open(private_key_path, 'w') as file:
            file.write(private_key)

        print('New JWS keypair successfully generated and written to disk.')


    def upload_client_csr_to_mcm(self, mcm_url, dfsp_name, csr_path, mcm_username, mcm_password):
        mcm_client = ConnectionManagerClient(mcm_url)

        try:
            print('Authenticating with hub MCM...')
            mcm_client.login(mcm_username, mcm_password)
            print('Successfully authenticated with hub MCM.')
            print('Uploading client certificate signing request...')

            with open(csr_path, "r") as file:
                csr = file.read()

            result = mcm_client.create_dfsp_inbound_enrollment(dfsp_name, {
                'clientCSR': csr,
            })

            if result['state'] != 'CSR_LOADED':
                print('Unexpected result state: {}'.format(result['state']))

            print('MCM validation results:')

            for v in result['validations']:
                print('validationCode: {}'.format(v['validationCode']))
                print('performed: {}'.format(v['performed']))
                print('result: {}'.format(v['result']))
                print('message: {}'.format(v['message']))
                print('data: {}'.format(v['data']))

        except Exception as e:
            print('Error occurred uploading CSR to MCM: {}'.format(e))


# this script can be called as a process with command line args
if __name__ == "__main__":
    if sys.argv[-1] == 'debug':
        input("hit a key after debugger attached")

    with PkiTools() as pkiTools:
        match sys.argv[1]:
            case 'generate_client_side_mtls':
                pkiTools.create_client_mtls_artefacts(sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5], sys.argv[6],
                                                      sys.argv[7], sys.argv[8])

            case 'generate_jws_keypair':
                pkiTools.create_jws_keypair(sys.argv[2], sys.argv[3], sys.argv[4])

            case 'upload_client_csr_to_mcm':
                pkiTools.upload_client_csr_to_mcm(sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[4])


