"""
One-time setup: creates dbo.watermark and seeds it with the max data_as_of
already loaded into dbo.governmental_rates, so the ADF incremental pipeline
only pulls genuinely new rows on its first run.
"""
import os

import pymssql

CREATE_SQL = """
IF OBJECT_ID('dbo.watermark', 'U') IS NULL
CREATE TABLE dbo.watermark (
    TableName NVARCHAR(100) PRIMARY KEY,
    WatermarkValue DATE
)
"""

SEED_SQL = """
IF NOT EXISTS (SELECT 1 FROM dbo.watermark WHERE TableName = 'governmental_rates')
INSERT INTO dbo.watermark (TableName, WatermarkValue)
SELECT 'governmental_rates', MAX(data_as_of) FROM dbo.governmental_rates
"""


def main() -> None:
    conn = pymssql.connect(
        server=os.environ["SQL_SERVER_FQDN"],
        user=os.environ["SQL_ADMIN_LOGIN"],
        password=os.environ["SQL_ADMIN_PASSWORD"],
        database=os.environ["SQL_DB_NAME"],
    )
    cur = conn.cursor()
    cur.execute(CREATE_SQL)
    cur.execute(SEED_SQL)
    conn.commit()
    cur.execute("SELECT * FROM dbo.watermark")
    print(cur.fetchall())
    conn.close()


if __name__ == "__main__":
    main()
