![](doc/299167953.gif)
![](doc/1437611472.gif)
![](doc/3896419641.gif)

## How To Use
* place `mapgenerator.exe` and the `RMG_resource` folder in the same folder than your gg2 executable.
* add the koth_random.gml plugin to your gg2 plugins
* at the end of a match, if the next map in your rotation is `koth_random`, `cp_random` or `dkoth_random` then the plugin will instead generate a map with the matching game mod
the first map loaded on a server won't be randomly generated (the client will try to get koth_random.png)

> **_NOTE:_** Modern version of Windows will understandably warns you when an unsigned executable is launched. It's possible to edit the gg2 plugin to refer to `mapgenerator.pyw` instead of the `.exe`, but you'll need to have python installed with the project's requirements.

http://www.ganggarrison.com/forums/index.php?topic=36721.0

Assets used for backgrounds by [Luis Zuno (@ansimuz)](https://www.patreon.com/ansimuz)
