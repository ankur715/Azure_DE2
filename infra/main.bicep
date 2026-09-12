// Resource-group scoped infra for the NYPA medallion pipeline.
// Deploy with:
//   az deployment group create -g <rg-name> -f infra/main.bicep -p sqlAdminPassword=<secret>

@description('Short prefix for all resource names, e.g. nypade2')
param namePrefix string = 'nypade2'

@description('Azure region for most resources')
param location string = resourceGroup().location

@description('Azure region for the SQL server — separate because some regions periodically stop accepting new SQL server creation. eastus/eastus2/westus2/southcentralus were all blocked at deploy time; centralus worked.')
param sqlLocation string = 'centralus'

@description('SQL admin login')
param sqlAdminLogin string = 'sqladmin'

@secure()
@description('SQL admin password — pass at deploy time, never commit it')
param sqlAdminPassword string

var storageAccountName = toLower('${namePrefix}dls${uniqueString(resourceGroup().id)}')
var dataFactoryName = '${namePrefix}-adf'
var sqlServerName = toLower('${namePrefix}-sql3-${uniqueString(resourceGroup().id)}')
var sqlDbName = 'nypa_rates'
var databricksWorkspaceName = '${namePrefix}-dbx'

resource storage 'Microsoft.Storage/storageAccounts@2023-01-01' = {
  name: storageAccountName
  location: location
  sku: { name: 'Standard_LRS' }
  kind: 'StorageV2'
  properties: {
    isHnsEnabled: true // ADLS Gen2 hierarchical namespace
    minimumTlsVersion: 'TLS1_2'
    allowBlobPublicAccess: false
  }
}

resource blobService 'Microsoft.Storage/storageAccounts/blobServices@2023-01-01' = {
  parent: storage
  name: 'default'
}

resource bronzeContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-01-01' = {
  parent: blobService
  name: 'bronze'
}

resource silverContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-01-01' = {
  parent: blobService
  name: 'silver'
}

resource goldContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-01-01' = {
  parent: blobService
  name: 'gold'
}

resource rawCsvContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-01-01' = {
  parent: blobService
  name: 'raw-csv'
}

resource dataFactory 'Microsoft.DataFactory/factories@2018-06-01' = {
  name: dataFactoryName
  location: location
  identity: { type: 'SystemAssigned' }
}

resource sqlServer 'Microsoft.Sql/servers@2023-05-01-preview' = {
  name: sqlServerName
  location: sqlLocation
  properties: {
    administratorLogin: sqlAdminLogin
    administratorLoginPassword: sqlAdminPassword
    minimalTlsVersion: '1.2'
  }
}

resource sqlDb 'Microsoft.Sql/servers/databases@2023-05-01-preview' = {
  parent: sqlServer
  name: sqlDbName
  location: sqlLocation
  sku: {
    name: 'Basic'
    tier: 'Basic'
  }
  properties: {
    maxSizeBytes: 2147483648
  }
}

// Allow Azure services (incl. ADF) through the SQL firewall
resource sqlFirewallAzure 'Microsoft.Sql/servers/firewallRules@2023-05-01-preview' = {
  parent: sqlServer
  name: 'AllowAzureServices'
  properties: {
    startIpAddress: '0.0.0.0'
    endIpAddress: '0.0.0.0'
  }
}

resource databricksWorkspace 'Microsoft.Databricks/workspaces@2024-05-01' = {
  name: databricksWorkspaceName
  location: location
  sku: { name: 'premium' } // premium needed for Unity Catalog; pause/delete clusters when idle to protect the credit
  properties: {
    managedResourceGroupId: subscriptionResourceId(
      'Microsoft.Resources/resourceGroups',
      '${namePrefix}-dbx-managed-rg'
    )
  }
}

output storageAccountName string = storage.name
output dataFactoryName string = dataFactory.name
output sqlServerFqdn string = sqlServer.properties.fullyQualifiedDomainName
output databricksWorkspaceUrl string = databricksWorkspace.properties.workspaceUrl
