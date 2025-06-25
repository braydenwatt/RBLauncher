# RBL: Dawn

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Platform](https://img.shields.io/badge/platform-macOS-lightgrey.svg)
![Python](https://img.shields.io/badge/python-3.7+-green.svg)

A custom Minecraft launcher built with PyQt5 that supports Fabric modloader, vanilla Minecraft, and Modrinth modpack integration. Features a modern, themeable interface with real-time log viewing and comprehensive instance management.

## Features

- **Multiple Instance Support**: Create and manage multiple Minecraft installations
- **Fabric Integration**: Automatic Fabric loader installation and configuration
- **Modrinth Support**: Direct modpack installation from Modrinth
- **Themeable Interface**: 4 built-in themes with support for customization
- **Real-time Logs**: View game logs with colored output in real-time
- **Account Management**: Microsoft account integration
- **Mod Management**: Easy mod installation and management
- **Instance Export/Import**: Share instances with others

## Installation

### Prerequisites

- **macOS** (primary platform)
- **Python 3.7+**
- **Java 8 or higher** (for Minecraft)
- **Git** (for cloning the repository)

### Setup

1. **Download the latest release:**
   [here](https://github.com/braydenwatt/RBLauncher/releases/tag/v1.0.0)

2. **Make launcher.command executable:**
   ```bash
   chmod +x /path/to/launcher.command
   ```

3. **Run the launcher:**
   ```bash
   /path/to/launcher.command
   ```
  NOTE:
   if the above does not work run:
   ```bash
   xattr -rc /path/to/launcher.command
   ```

## Usage Guide

### First Launch

1. **Set up your account**: Click "Account" to add your Microsoft account
2. **Configure Java path**: Go to Settings to set your Java installation path
3. **Choose a theme**: Use the Theme dropdown to select your preferred appearance

### Creating Instances

#### Vanilla Minecraft
1. Click "Add Instance"
2. Select "Vanilla" tab
3. Choose your Minecraft version
4. Enter instance name
5. Click "Create Instance"

#### Fabric Modded
1. Click "Add Instance"
2. Select "Fabric" tab
3. Choose Minecraft version and Fabric loader version
4. Enter instance name
5. Click "Create Instance"

#### Modrinth Modpacks
1. Click "Add Instance"
2. Select "Modrinth" tab
3. Search for modpacks
4. Select version and configure settings
5. Click "Create Instance"

### Managing Instances

- **Launch**: Select instance and click "Launch"
- **View Logs**: Click "Show/Hide Logs" to monitor game output
- **Edit**: Modify instance settings, version, or modloader
- **Install Mods**: Use "Manage Mods" for easy mod installation
- **Open Folder**: Access instance files directly
- **Export/Copy**: Share instances or create backups
- **Delete**: Remove unwanted instances

## Troubleshooting

### Common Issues

#### "Java not found" Error
**Problem**: Launcher can't locate Java installation

**Solutions**:
1. Install Java 21 JDK from Self Service
2. Set Java path manually in Settings
3. Ensure Java is in your system PATH:
   ```bash
   echo $PATH
   java -version
   ```

#### Instance Won't Launch
**Problem**: Instance fails to start or crashes immediately

**Solutions**:
1. Check Java version compatibility (Java 8+ for modern MC versions)
2. Verify instance configuration in Edit Instance
3. Check logs for specific error messages
4. Ensure sufficient RAM allocation
5. Try recreating the instance

#### Fabric Installation Failed
**Problem**: Fabric loader installation doesn't complete

**Solutions**:
1. Check internet connection
2. Verify Minecraft version and Fabric version compatibility
3. Manually delete instance folder and recreate
4. Check Java permissions and PATH
5. Try different Fabric loader version

#### Mods Not Loading
**Problem**: Installed mods don't appear in-game

**Solutions**:
1. Verify mods are Fabric-compatible (not Forge)
2. Check mod version matches Minecraft version
3. Ensure Fabric API is installed if required
4. Check mod dependencies
5. Remove conflicting mods

#### Account Login Issues
**Problem**: Cannot authenticate with Microsoft account

**Solutions**:
1. Check internet connection
2. Verify Microsoft account credentials

### File Locations

- **Config**: `~/.minecraft_launcher_config.json`
- **Game Directory**: `~/Library/Application Support/ReallyBadLauncher`
- **Instances**: `~/Library/Application Support/ReallyBadLauncher/instances/`
- **Logs**: Check real-time logs in launcher

### Debug Mode

Enable verbose logging by running:
```bash
python new_launcher.py --debug
```

### Reset Configuration

If the launcher becomes corrupted:
```bash
rm ~/.minecraft_launcher_config.json
rm -rf ~/Library/Application\ Support/ReallyBadLauncher
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Support

- **Issues**: [GitHub Issues](https://github.com/braydenwatt/RBLauncher/issues)

---

**Note**: This launcher is unofficial and not affiliated with Mojang Studios or Microsoft. Minecraft is a trademark of Mojang Studios.
