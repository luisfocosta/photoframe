# PowerShell script to download EdgeDriver for version 142.0.3595.53
$version = "142.0.3595.53"
$url = "https://msedgedriver.azureedge.net/$version/edgedriver_win64.zip"

Write-Host "Attempting to download EdgeDriver version $version"

try {
    # Try the primary URL
    Invoke-WebRequest -Uri $url -OutFile "edgedriver_$version.zip"
    Write-Host "Downloaded successfully from primary URL"
} catch {
    Write-Host "Primary URL failed: $($_.Exception.Message)"
    
    # Try alternative GitHub URL pattern
    $githubUrl = "https://github.com/MicrosoftDocs/edge-developer/releases/download/$version/edgedriver_win64.zip"
    try {
        Invoke-WebRequest -Uri $githubUrl -OutFile "edgedriver_$version.zip"
        Write-Host "Downloaded successfully from GitHub URL"
    } catch {
        Write-Host "GitHub URL also failed: $($_.Exception.Message)"
        
        # Try the legacy msedgewebdriverstorage URL
        $legacyUrl = "https://msedgewebdriverstorage.blob.core.windows.net/edgewebdriver/$version/edgedriver_win64.zip"
        try {
            Invoke-WebRequest -Uri $legacyUrl -OutFile "edgedriver_$version.zip"
            Write-Host "Downloaded successfully from legacy URL"
        } catch {
            Write-Host "All download attempts failed: $($_.Exception.Message)"
            exit 1
        }
    }
}

# Extract the zip file
if (Test-Path "edgedriver_$version.zip") {
    Write-Host "Extracting EdgeDriver..."
    Expand-Archive -Path "edgedriver_$version.zip" -DestinationPath "temp_extract" -Force
    
    # Copy the driver to replace the old one
    if (Test-Path "temp_extract\msedgedriver.exe") {
        Copy-Item "temp_extract\msedgedriver.exe" "msedgedriver.exe" -Force
        Write-Host "EdgeDriver updated successfully!"
        
        # Clean up
        Remove-Item "edgedriver_$version.zip" -Force
        Remove-Item "temp_extract" -Recurse -Force
    } else {
        Write-Host "msedgedriver.exe not found in the extracted files"
        exit 1
    }
} else {
    Write-Host "Download failed - zip file not found"
    exit 1
}