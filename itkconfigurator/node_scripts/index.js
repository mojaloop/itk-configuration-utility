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

const util = require('util');
const { McmClientManager } = require('./mcmClient.js');

const test = async () => {
    console.log('Testing mcm client functions...');

    const opts = {
        initFileName: '../vaultinit.json',
        mojaloopConnectorFQDN: 'test.com',
        vaultContainerName: '/itk-configurator-vault1',
        stateMachineDebugPort: 8081,
        dfspId: 'somedfsp',
        mcmServerEndpoint: '',
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
    return mc;
};

const generateClientSideMtls = async(dfspName, caCertPath, serverCertPath, serverKeyPath,
                                     clientCertPath, clientKeyPath, dnsNames, mcmEndpoint) => {
    console.log('Generating client side mTLS artefacts...');

    const opts = {
        initFileName: '../vaultinit.json',
        mojaloopConnectorFQDN: dnsNames,
        vaultContainerName: '/itk-configurator-vault1',
        stateMachineDebugPort: 4444,
        dfspId: dfspName,
        mcmServerEndpoint: mcmEndpoint,
        hubIamProviderUrl: 'http://localhost:8080',
        oidcScope: 'email',
        oidcTokenRoute: 'auth/realms/dfsps/protocol/openid-connect/token',
        auth: {
            enabled: true,
            creds: {
                clientId: 'testdfsp',
                clientSecret: '9249fde4-c1c9-4447-9c46-784f01ca4309',
            },
        },
        vault: {
            endpoint: 'http://127.0.0.1:8200',
            mounts: {
                pki: 'pki',
                kv: 'secrets',
            },
            pkiServerRole: 'example.com',
            pkiClientRole: 'example.com',
            signExpiryHours: '43800',
            keyLength: 4096,
            keyAlgorithm: 'rsa',
        }
    };

    const mc = new McmClientManager(opts);

    try {
        await mc.connect();
        await mc.startStateMachine();
        await mc.onboardDfsp();
    }
    catch(err) {
        console.log(`Error in generateClientSideMtls: ${util.inspect(err)}`);
        throw err;
    }

    return mc;
}


const main = async () => {
    let mc;

    switch (process.argv[2]) {
        case 'test':
            mc = await test();
            break;

        case 'generate_client_side_mtls':
            mc = await generateClientSideMtls(process.argv[3], process.argv[4], process.argv[5], process.argv[6],
                process.argv[7], process.argv[8], process.argv[9], process.argv[10], );
            break;

        default:
            throw new Error(`Unknown command: {${process.argv[2]}`);
    }

    if(mc) {
        mc.disconnect();
    }
}

main().then(() => {
    console.log('Process complete.');
});
