# Mojaloop ITK Configurator

This is a simple terminal utility which provides features to simplify the process of configuring and managing components
of the Mojaloop Integration Toolkit such as:

- Mojaloop Connector
    - Configure scheme connection settings including all security elements.
- Core Connector
    - Configure connection and integration with your backend systems.

## Installation

### Pre-requisites

- Python 3.11+
- Docker (desktop or equivalent necessary to run docker containers locally)
    - Note that this utility uses Hashicorp Vault as a docker container for performing cryptographic operations. You
      should ensure that your user account has permissions to run docker commands.

### Installation Steps

1. Clone this repository locally.
2. Build the project:

```bash
$ python -m build
```

3. Install the project

```bash
$ pip install ./dist/mojaloop_itk_configurator-1.0.0.tar.gz
```

You can now run the configuration utility thus:

```bash
$ itkconfigurator
```

## Uninstallation

To uninstall the project after a pip install run the following command from the terminal:

```bash
$ pip uninstall mojaloop-itk-configurator
```

## Developing / Debugging

If your development environment does not support automatically attaching to spawned python subprocesses, you can run the
files e.g. pkitools.py independantly. Pass "debug" as the final command line arg and the process will pause to allow you
to attach a debugger.