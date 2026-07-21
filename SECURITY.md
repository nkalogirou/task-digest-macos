# Security policy

## Supported version

Security fixes are applied to the latest release on the `main` branch.

## Reporting a vulnerability

Please do not open a public issue for vulnerabilities that could expose credentials, local dashboard controls, private task data, or filesystem access.

Use GitHub private vulnerability reporting when enabled. If it is unavailable, contact the repository maintainer privately through the address listed in the maintainer's GitHub profile.

Include:

- affected version or commit;
- macOS and Python version;
- clear reproduction steps;
- expected and actual behavior;
- impact assessment;
- a proposed fix, if available.

Do not include real tokens, authentication codes, private comments, backup archives, or company data.

## Security boundaries

Task Digest assumes:

- a trusted local macOS account;
- a dashboard bound to `127.0.0.1`;
- Asana credentials stored in Keychain;
- GitHub credentials managed by `gh`;
- local runtime files kept outside source control.

Running the dashboard on a non-loopback interface is outside the supported threat model.
