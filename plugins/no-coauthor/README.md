# No Claude Attribution

Automatically removes Claude co-author trailers, `Claude-Session:` trailers and generated/created-by footers before Git commits and GitHub writes. Human co-authors and ordinary references to Claude stay intact.

The `PreToolUse` hook handles Bash commands (including RTK wrappers), heredocs, repeated `-m`, escaped newlines, `--trailer`, `gh --body`, Git `-F`/`--file`, and `gh --body-file`. File inputs use a cleaned stream when the command runs; original message files are never edited. It also handles `body`, `message` and `commit_message` fields on GitHub MCP write tools. Python 3 is required; tests also require Bash, Git and jq.

## Local install

From this repository:

```sh
python3 plugins/no-coauthor/scripts/install-local.py
```

The installer registers this plugin folder as the dedicated `no-coauthor-local` marketplace, installs this plugin through Claude's CLI, and sets personal `attribution.commit` and `attribution.pr` to empty strings. It disables the older `no-coauthor@anetrebskii` installation and leaves other marketplace plugins on their existing sources. It backs up settings and registration files under the printed temporary directory.

If the standard user RTK rewrite hook is configured, the installer moves it into this plugin's `rtk_hook` option. RTK runs first, attribution cleanup runs last, and the existing RTK permission decision is preserved. This avoids two parallel hooks overwriting each other's commands. Other hooks remain unchanged. An attribution-only commit message is denied so Claude retries with a descriptive message.

Restart Claude Code after installing. Local settings and plugins apply to sessions on this machine. Cloud sessions need their own installation or committed project configuration. Already-pushed commits and GitHub's server-side squash messages are not rewritten.

## Tests

```sh
bash plugins/no-coauthor/tests/run.sh
python3 plugins/no-coauthor/tests/test_hook.py
```

The file argument handler supports literal paths in the tool's working directory. Use an absolute message-file path when a command changes directory with `cd` or `git -C`. Shell-expanded filenames, stdin assembled outside the command, and arbitrary external programs are outside the hook's coverage.
