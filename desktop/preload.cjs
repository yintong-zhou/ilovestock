// pin.html's one call: send the chosen PIN to the main process, which checks who sent it.
const { contextBridge, ipcRenderer } = require('electron')

contextBridge.exposeInMainWorld('ilovestock', { setPin: (pin) => ipcRenderer.send('pin', pin) })
