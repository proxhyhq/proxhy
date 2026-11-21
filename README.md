# Proxhy

This repository contains the [Proxhy](https://proxhy.com) source code.

| I'm...                            | Go here                                                   |
| --------------------------------- | --------------------------------------------------------- |
| **a user**                        | [proxhy.com](https://proxhy.com)                          |
| **looking for the launcher code** | [proxhyhq/launcher](https://github.com/proxhyhq/launcher) |
| **a developer**                   | keep reading ↓                                            |

## For Developers

### Contributing to Proxhy

See [contributing.md](./CONTRIBUTING.md).

### Libraries

Developing Proxhy has led to the creation of various different libraries that may be useful outside the project itself.

#### petty

[source](./petty)

Portmanteau of Python and [netty](https://netty.io/) :). A networking library for Minecraft 1.8.9 built in Python and Rust that provides the building blocks for custom clients, server, and proxies. Petty handles the packet serialization, encryption, compression, and connection state.

#### mcauth

[source](./mcauth)

An asynchronous Python library for authenticating Minecraft accounts.

#### compass

[source](./compass)

A peer discovery and rendezvous service that links verified Minecraft accounts to [Iroh](https://iroh.computer) endpoint identities so players can connect directly without trading network addresses. It supports session authentication, configurable discoverability, whitelisting, and connection requests, which Proxhy utilizes primarily to enable live game broadcasting.

#### coral

[source](https://github.com/proxhyhq/coral)

A lightweight asynchronous Python client for the [Coral](https://urchin.gg/) API.

#### pyroh

[source](https://github.com/kbidlack/pyroh)
An asyncio-compatible Python wrapper for the iroh p2p networking library.
