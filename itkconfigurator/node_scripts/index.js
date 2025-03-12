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

const { McmClientManager } = require('./mcmClient.js');

const test = async () => {
    console.log('Testing mcm client functions...');

    const opts = {
        initFileName: '../vaultinit.json',
        mojaloopConnectorFQDN: 'test.com',
        vaultContainerName: '/itk-configurator-vault1',
        stateMachineDebugPort: 8081,
        vault: {
            endpoint: 'http://127.0.0.1:8200',
            mounts: {
                pki: 'pki',
                kv: 'secrets',
            },
            pkiServerRole: 'example.com',
            pkiClientRole: 'example.com',
            auth: {
                appRole: {
                    roleId: '348c874d-22a6-7d34-94a9-201802093dd4',
                    roleSecretId: '1029d634-64f3-c943-1558-34ad681b0f3d',
                },
            },
            signExpiryHours: '43800',
            keyLength: 4096,
            keyAlgorithm: 'rsa',
        }
    };

    const mc = new McmClientManager(opts);
    await mc.connect();
};


const main = async () => {
    switch (process.argv[2]) {
        case 'test':
            await test();
            break;

        default:
            throw new Error(`Unknown command: {${process.argv[2]}`);
    }
}

main();