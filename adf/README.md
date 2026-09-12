ADF linked service / dataset / pipeline JSON, exported for reference.

`linkedService/*.json` use placeholders (`<STORAGE_ACCOUNT_NAME>`, `<SQL_SERVER_FQDN>`,
`<KEY_VAULT_NAME>`, `<SQL_ADMIN_LOGIN>`) instead of the real values from this project's
live deployment — swap in your own before running
`az datafactory linked-service create --properties @<file>`. Nothing sensitive (the SQL
password) is ever in these files; it's resolved at runtime from Key Vault via the
`AzureKeyVaultSecret` reference in `LS_AzureSqlDb.json`.
