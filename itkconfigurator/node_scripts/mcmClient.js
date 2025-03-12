/*************************************************************************
 *  (C) Copyright Mojaloop Foundation. 2024 - All rights reserved.        *
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
const { Vault, ConnectionStateMachine } = require('@pm4ml/mcm-client');
const { Logger } = require('@mojaloop/sdk-standard-components');
const Docker = require('dockerode');

const constants = {
    vaultImageName: 'hashicorp/vault',
    containerStartTimeoutSecs: 60,
    vaultInitFile: 'vaultinit.json',
}


/**
 * Encapsulates functions for manipulating a Vault docker container including initialization
 * and initial setup for use as a key store for local integration tools which communicate with
 * hub side "Mojaloop Connection Manager" (MCM) server.
 */
class VaultDocker {
    constructor({ containerName, logger, vaultClient, vaultInitFileName }) {
        this.constants = constants;

        this.containerName = containerName;
        this.logger = logger;
        this.vaultClient = vaultClient;
        this.vaultInitFileName = vaultInitFileName;

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
            .find(c => c.Names.includes(this.constants.vaultContainerName));

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

            // create an appRole and store the role-id and secret-id
            await this.enableAppRoleAuth();
            this.vaultInitFile.appRole = await this.createAppRole();
            await this.tryWriteVaultInitFile(this.vaultInitFileName, this.vaultInitFile);

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
        });

        await this.vaultDocker.startVaultContainer();
        await this.vaultDocker.waitForVaultContainerHealthy();
        const vaultInitFile = await this.vaultDocker.initializeVault();

        this.vault.setAuth({
            appRole:{
                roleId: vaultInitFile.appRole.role_id,
                roleSecretId: vaultInitFile.appRole.secret_id
            },
        });
        await this.vault.connect();

        this.logger.debug('Connected to vault.')
    }

    async startStateMachine() {
        const stateMachine = new ConnectionStateMachine({
            dfspId: config.dfspId,
            hubEndpoint: config.mcmServerEndpoint,
            dfspCertificateModel: new DFSPCertificateModel(opts),
            hubCertificateModel: new HubCertificateModel(opts),
            hubEndpointModel: new HubEndpointModel(opts),
            dfspEndpointModel: new DFSPEndpointModel(opts),
            port: this.config.stateMachineDebugPort,
            logger: this.logger,
            vault: this.vault,
            certManager: undefined,
            ControlServer: undefined,
        });

        await stateMachine.start();
    }
}


module.exports = {
    McmClientManager,
};
