# Removing Secrets from Git and Rotating Credentials

This file provides exact commands to detect files currently tracked that should be ignored, remove them from the index, and optionally purge them from history using `git-filter-repo` or the BFG Repo-Cleaner. Use the destructive history-rewrite commands only if you understand the ramifications (force-push required, collaborators must re-clone).

1) Detect sensitive files currently tracked

```bash
# list tracked files that match common secret names
git ls-files | egrep "(\.env|gmail_credentials.json|gmail_token.json|elderly_healthcare.db|\.agent_credentials.json)"

# show recent commits touching those files
git log --stat --follow -- <path/to/file>
```

2) Remove files from the index (non-destructive)

This removes files from the index in the next commit but keeps them in history.

```bash
git rm --cached .env gmail_credentials.json gmail_token.json elderly_healthcare.db .agent_credentials.json || true
git commit -m "Remove local secret files from index"
git push origin main
```

3) Purge files from history (recommended if secrets were pushed)

Preferred: `git-filter-repo` (fast and robust)

```bash
pip install git-filter-repo

# Make a bare clone and run filter-repo
git clone --mirror https://github.com/your-org/your-repo.git repo.git
cd repo.git
git filter-repo --invert-paths --paths .env --paths gmail_credentials.json --paths gmail_token.json --paths elderly_healthcare.db --paths .agent_credentials.json

# Push the rewritten history (force)
git push --force --all
git push --force --tags
```

Alternative: BFG Repo-Cleaner (simpler for common cases)

```bash
# Download BFG jar from https://rtyley.github.io/bfg-repo-cleaner/
git clone --mirror https://github.com/your-org/your-repo.git repo.git
java -jar bfg.jar --delete-files ".env,gmail_credentials.json,gmail_token.json,elderly_healthcare.db,.agent_credentials.json" repo.git
cd repo.git
git reflog expire --expire=now --all && git gc --prune=now --aggressive
git push --force
```

4) After history rewrite — collaborator instructions

- Everyone must re-clone the repository after a forced history rewrite. Old clones still contain secrets.

5) Credential rotation checklist

- Gmail OAuth client: regenerate client secret and re-run `setup_gmail.py` to obtain new tokens.
- SMTP credentials / App Passwords: revoke and create new App Passwords.
- VAPID keys: generate a new key pair and update subscribers.
- JWT secrets: replace `JWT_SECRET_KEY` and reissue tokens as needed.
- Any cloud provider keys (Render, AWS, GCP): rotate from their consoles.

6) Verification

- After purging, verify no secret files remain in the remote by cloning the repo to a temp directory and running the detection command from step 1.

7) Notes

- Do not add secret files back into the repository. Use environment variables or secret stores.
- Consider using a secrets manager (HashiCorp Vault, AWS Secrets Manager, Render secrets) for production.
