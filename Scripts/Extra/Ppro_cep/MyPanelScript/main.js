//main.js
function runJsx(scriptFile) {
    var csInterface = new CSInterface();
    var extensionPath = csInterface.getSystemPath(SystemPath.EXTENSION);
    var fullPath = extensionPath + "/jsx/" + scriptFile;

    fullPath = fullPath.replace(/\\/g, "\\\\"); // Для Windows

    var script = `$.evalFile("${fullPath}")`;
    csInterface.evalScript(script);
}
