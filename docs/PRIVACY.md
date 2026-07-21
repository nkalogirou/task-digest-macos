# Privacy and security

Task Digest is a local personal tool, not a hosted service.

## Data flows

Task Digest reads data from:

- the Asana REST API using the token in macOS Keychain;
- GitHub through the locally authenticated GitHub CLI;
- local JSON state stored inside the project directory.

It sends data only when you explicitly enable Asana write actions and use one of those controls. GitHub integration is read-only in the current implementation.

## Local storage

The following can contain work metadata and should remain private:

- `.env`
- `state/*.json`
- `history/*`
- `backups/*.zip`
- `logs/*.log`
- `output/*.html`

They are ignored by Git. Do not force-add them.

## Credentials

- The Asana token is stored as a generic password in the macOS login Keychain.
- GitHub credentials are managed by GitHub CLI.
- The dashboard action token is generated locally in `state/dashboard_token` and ignored by Git.
- Backups remove any `ASANA_TOKEN=` fallback line from `.env`.

## Dashboard exposure

The default host is `127.0.0.1`, which makes the server available only from the local Mac.

Changing the host to `0.0.0.0` can expose task names, comments, links, notes, controls, and local data to other devices on the network. Task Digest is not designed to be internet-facing. Keep the loopback default.

## Write actions

The public configuration defaults to:

```dotenv
ENABLE_ASANA_WRITE_ACTIONS=false
```

When enabled, dashboard controls can modify Asana tasks. Confirmation is required for destructive changes, but users should still review permissions and test on non-critical tasks first.

## Logs and issue reports

Before attaching logs to a public issue, review them for:

- organization and repository names;
- task titles and comments;
- Asana/GitHub URLs;
- usernames and email addresses;
- filesystem paths.

Never post tokens, one-time authentication codes, `.env`, Keychain output, or backup archives.
