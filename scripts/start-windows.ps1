$ErrorActionPreference = "Stop"

$appName = "pm-app"
$imageName = "pm-app"
$rootDir = Resolve-Path "$PSScriptRoot\.."

docker build -t $imageName $rootDir

# Remove existing container if it exists (ignore if it doesn't)
try {
    docker rm -f $appName
} catch {
    # Container doesn't exist, which is fine
}

docker run --name $appName --env-file "$rootDir\.env" -p 8000:8000 $imageName
