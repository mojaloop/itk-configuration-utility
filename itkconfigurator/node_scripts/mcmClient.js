/*************************************************************************
 *  (C) Copyright Mojaloop Foundation. 2025 - All rights reserved.        *
 *                                                                        *
 *  This file is made available under the terms of the license agreement  *
 *  specified in the corresponding source code repository.                *
 *                                                                        *
 *  ORIGINAL AUTHOR:                                                      *
 *       James Bush - jbush@mojaloop.io                                   *
 *                                                                        *
 *  CONTRIBUTORS:                                                         *
 *       James Bush - jbush@mojaloop.io                                   *
 *************************************************************************/

const fs = require('fs').promises;
const util = require('util');
const { Logger } = require('@mojaloop/sdk-standard-components');
const Docker = require('dockerode');
const {
    AuthModel,
    DFSPCertificateModel,
    DFSPEndpointModel,
    HubCertificateModel,
    HubEndpointModel,
    Vault,
    ConnectionStateMachine,
    ControlServer,
} = require('@pm4ml/mcm-client');


const vaultPolicy = `
path "sys/mounts/*" {
    capabilities = ["create", "read", "update", "delete", "list"]
}

path "sys/mounts" {
    capabilities = ["read", "list"]
},

path "pki*" {
    capabilities = ["create", "read", "update", "delete", "list", "sudo", "patch"]
},

path "kvenginemountpoint*" {
    capabilities = ["create", "read", "update", "delete", "list", "sudo", "patch"]
}`;

const constants = {
    vaultImageName: 'hashicorp/vault',
    containerStartTimeoutSecs: 60,
    vaultInitFile: 'vaultinit.json',
    vaultPolicy,
}


/**
 * Encapsulates functions for manipulating a Vault docker container including initialization
 * and initial setup for use as a key store for local integration tools which communicate with
 * hub side "Mojaloop Connection Manager" (MCM) server.
 */
class VaultDocker {
    constructor({ containerName, logger, vaultClient, vaultInitFileName, mounts, pkiRoles }) {
        this.constants = constants;

        this.containerName = containerName;
        this.logger = logger;
        this.vaultClient = vaultClient;
        this.vaultInitFileName = vaultInitFileName;
        this.mounts = mounts;
        this.pkiRoles = pkiRoles;

        this.docker = new Docker();
    }

    async startVaultContainer() {
        // read any existing vault config
        this.vaultInitFile = await this.tryReadVaultInitFile(this.vaultInitFileName);

        // does the container already exist?
        const containers = await this.docker.listContainers({
            all: true,
        });

        const vaultContainerInfo = containers
            .find(c => c.Names.includes(this.containerName));

        if (!vaultContainerInfo) {
            // we need to create the container
            return this.createVaultContainer();
        }

        const vaultContainerObject = this.docker.getContainer(vaultContainerInfo.Id);

        if (vaultContainerInfo.State === 'exited') {
            // we need to start the container
            this.logger.debug('Starting vault container...');
            try {
                await vaultContainerObject.start({});
                this.logger.debug('Started vault container.');
            }
            catch(err) {
                this.logger.error(`Error starting vault container: ${err}`);
            }
        }
    }

    async createVaultContainer() {
        try {
            this.logger.debug('Creating vault container...');

            const vaultStoragePath = await fs.realpath('../vaultfile');

            const container = await this.docker.createContainer({
                Image: this.constants.vaultImageName,
                Cmd: ['server'],
                Env: [
                    //
                    'VAULT_LOCAL_CONFIG={"storage": {"file": {"path": "/vault/file"}}, "listener": [{"tcp": { "address": "0.0.0.0:8200", "tls_disable": true}}], "default_lease_ttl": "168h", "max_lease_ttl": "720h", "ui": true}',
                ],
                HostConfig: {
                    CapAdd: ["IPC_LOCK"],
                    PortBindings: {
                        "8200/tcp": [{HostPort: "8200"}]
                    },
                    Binds: [`${vaultStoragePath}:/vault/file:rw`],
                },
                name: this.containerName.slice(1),
            });

            await container.start();
        }
        catch(err) {
            this.logger.error(`Error creating vault container ${err}`);
        }
    }

    async waitForVaultContainerHealthy() {
        const startTime = Date.now();

        while (Date.now() - startTime < (this.constants.containerStartTimeoutSecs * 1000)) {
            try {
                // if we can read the seal status then the container is up.
                // if this call throws, the container is down, so we try again.
                const res = await this.vaultClient.readSealStatus();
                this.logger.debug(`Vault status: ${util.inspect(res)}`);
                return true;
            }
            catch(err) {
                this.logger.error(`Error reading vault status: ${err}. Retrying.`);
                // wait 1 second before retrying
                await new Promise(resolve => setTimeout(resolve, 1000));
            }
        }

        throw new Error("Timed out waiting for vault container to start.");
    }

    async initializeVault() {
        this.logger.debug('Initializing vault...')

        try {
            const res = await this.vaultClient.initialize({
                secret_shares: 1,
                secret_threshold: 1,
            });

            this.logger.debug(`Vault init result: ${util.inspect(res)}`);

            this.vaultInitFile = res;
            await this.tryWriteVaultInitFile(this.vaultInitFileName, res);

            await this.unsealVault();

            //await this.vaultClient.mountAll();

            // update our default policy
            const defaultPolicy = await this.getVaultPolicy('default');
            const newPolicy = `${defaultPolicy.rules}\n${constants.vaultPolicy
                .replaceAll('kvenginemountpoint', this.mounts.kv)}`;
            await this.updateVaultPolicy('default', newPolicy);

            // create an appRole and store the role-id and secret-id
            await this.enableAppRoleAuth();
            this.vaultInitFile.appRole = await this.createAppRole();
            await this.tryWriteVaultInitFile(this.vaultInitFileName, this.vaultInitFile);

            await this.vaultClient.mountAll(this.vaultInitFile.root_token);
            await this.createPkiRoles(this.pkiRoles)

            return this.vaultInitFile;
        }
        catch(err) {
            if(err.message !== 'Vault is already initialized') {
                // unexpected error, rethrow after logging.
                this.logger.error(`Error attempting to initialize vault: ${util.inspect(err)}`);
                throw err;
            }
        }

        // we get here if the vault is already initialized. just unseal.
        await this.unsealVault();
        return this.vaultInitFile;
    }

    async createPkiRoles(roles) {
        return Promise.all(roles.map(r => {
            return this.vaultClient.createPkiRole(this.vaultInitFile.root_token, r, {
                allowed_domains: '*',
                allow_any_name: true,
                allow_bare_domains: true,
                allow_subdomains: true,
                max_ttl: '60h',
                key_bits: 4096,
            })
        }));
    }

    async getVaultPolicy(policyName) {
        return this.vaultClient.getPolicy(this.vaultInitFile.root_token, policyName);
    }

    async updateVaultPolicy(policyName, policy) {
        return this.vaultClient.updatePolicy(this.vaultInitFile.root_token, policyName, policy);
    }

    async enableAppRoleAuth() {
        this.logger.debug('Enabling approle authentication...');

        try {
            const res = await this.vaultClient.enableAppRoleAuth(this.vaultInitFile.root_token);
            this.logger.debug(`Enabled approle auth: ${util.inspect(res)}`);
        }
        catch(err) {
            this.logger.error(`Error enabling approle auth: ${util.inspect(err)}`);
            throw err;
        }
    }

    async createAppRole() {
        this.logger.debug('Creating vault app role...');

        try {
            const res = await this.vaultClient.createAppRole(this.vaultInitFile.root_token, {
                role_name: 'itk-configurator-app',
                token_type: 'service',
                token_ttl: '10m',
                token_max_ttl: '15m',
                token_policies: 'default',
            });

            this.logger.debug(`Created vault app role: ${util.inspect(res)}`);
            return res;
        }
        catch(err) {
            this.logger.error(`Error creating app role: ${util.inspect(err)}`);
            throw err;
        }
    }

    async unsealVault() {
        const unsealRes = await this.vaultClient.unseal({
            key: this.vaultInitFile.keys[0],
        });

        this.logger.debug(`Vault unseal result: ${util.inspect(unsealRes)}`);

        if(unsealRes.sealed) {
            throw new Error('Vault unseal failed. Vault is still sealed.')
        }
    }

    async tryReadVaultInitFile(filename) {
        const data = await fs.readFile(filename, 'utf-8');
        return JSON.parse(data);
    }

    async tryWriteVaultInitFile(filename, data) {
        return fs.writeFile(filename, JSON.stringify(data, null, 4));
    }
}


class McmClientManager {
    constructor(config) {
        this.config = config;
        this.logger = new Logger.Logger();
    }

    async connect() {
        this.logger.debug('Initializing vault connection...')
        this.vault = new Vault({
            ...this.config.vault,
            commonName: this.config.mojaloopConnectorFQDN,
            logger: this.logger,
        });

        this.vaultDocker = new VaultDocker({
            logger: this.logger,
            vaultClient: this.vault,
            containerName: this.config.vaultContainerName,
            vaultInitFileName: this.config.initFileName,
            mounts: this.config.vault.mounts,
            pkiRoles: [this.config.vault.pkiServerRole, this.config.vault.pkiClientRole],
        });

        await this.vaultDocker.startVaultContainer();
        await this.vaultDocker.waitForVaultContainerHealthy();
        const vaultInitFile = await this.vaultDocker.initializeVault();

        this.vault.setAuth({
            appRole:{
                roleId: vaultInitFile.appRole?.role_id,
                roleSecretId: vaultInitFile.appRole?.secret_id
            },
        });
        await this.vault.connect();

        this.logger.debug('Connected to vault.')
    }

    disconnect() {
        this.logger.debug('Disconnecting from vault...');
        this.vault.disconnect();
        this.stateMachine.stop();
        this.logger.debug('Disconnected.');
    }

    async startStateMachine() {
        const modelOpts = {
            dfspId: this.config.dfspId,
            hubEndpoint: this.config.mcmServerEndpoint,
            logger: this.logger,
            hubIamProviderUrl: this.config.hubIamProviderUrl,
            auth: this.config.auth,
            oidcScope: this.config.oidcScope,
        };

        // login to MCM server
        const authModel = new AuthModel({
            logger: this.logger,
            auth: this.config.auth,
            hubIamProviderUrl: this.config.hubIamProviderUrl,
            oidcTokenRoute: this.config.oidcTokenRoute,
        });

        try {
            await authModel.login();
        } catch (err) {
            this.logger.error(`Error logging in to MCM server: ${util.inspect(err)}`);
            throw err;
        }

        this.stateMachine = new ConnectionStateMachine({
            dfspId: this.config.dfspId,
            refreshIntervalSeconds: 5,
            hubEndpoint: this.config.mcmServerEndpoint,
            dfspCertificateModel: new DFSPCertificateModel(modelOpts),
            hubCertificateModel: new HubCertificateModel(modelOpts),
            hubEndpointModel: new HubEndpointModel(modelOpts),
            dfspEndpointModel: new DFSPEndpointModel(modelOpts),
            port: this.config.stateMachineDebugPort,
            logger: this.logger,
            vault: this.vault,
            certManager: undefined,
            ControlServer,
            config: {
                stateMachineDebugPort: this.config.stateMachineDebugPort,
                stateMachineInspectEnabled: true,
                whitelistIP: ['1.2.3.4'],
                callbackURL: 'connector.testdfsp.com:443',
                dfspServerCsrParameters: {
                    subject: {
                        CN: 'testdfsp.com',
                        OU: '',
                        O: '',
                        L: '',
                        C: '',
                        ST: '',
                    },
                    extensions: {
                        subjectAltName: {
                            dns: [],
                            ips: [],
                        },
                    },
                },
            },
        });

        this.stateMachine.start();
    }

    async onboardDfsp() {
        const prom = new Promise(resolve => {
            const sub = this.stateMachine.service.subscribe({
                next(snapshot) {
                    //console.log(`Statemachine snapshot: ${util.inspect(snapshot, { depth: 5 })}`);
                    console.log(`Statemachine snapshot: ${new Date().toISOString()}: ${util.inspect(snapshot.value)}`);
                },
                error(err) {
                    console.log(`Statemachine error: ${util.inspect(err, { depth: 5 })}`);
                    resolve();
                },
                complete() {
                    console.log('Statemachine complete');
                    resolve();
                }
            });
        });

        this.stateMachine.sendEvent({type: 'CREATE_INT_CA', subject: this.config.dfspId});

        await prom;
    }
}


module.exports = {
    McmClientManager,
};
