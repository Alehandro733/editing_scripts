/* global $, CSInterface */
(function (window) {
  'use strict';

  /**
   * Editors module: wires up the on-panel JavaScript editor (CEP runtime)
   * and the ExtendScript editor (host, e.g. Premiere Pro).
   * Usage: Editors.setupEditors({ cs, $, logJS, logJSX, logJSExec })
   */
  function setupEditors(deps) {
    if (!deps || !deps.cs || !deps.$) {
      console.error('[Editors] Missing deps: need cs and $');
      return;
    }
    var cs = deps.cs;
    var $ = deps.$;
    var logJS = deps.logJS || function () {};
    var logJSX = deps.logJSX || function () {};
    var logJSExec = deps.logJSExec || logJS;

    // Cache DOM
    var $jsxEditor = $('#jsx-editor');
    var $runJsxCode = $('#run-jsx-code');
    var $jsEditor  = $('#js-editor');
    var $runJsCode = $('#run-js-code');

    // ========================================================================
    // SAFE eval for ExtendScript (JSX)  — moved from app.js
    // ========================================================================
    function evalScript_Safe(code) {
      var j = function (str) { try { return JSON.stringify(str); } catch (e) { return '""'; } };
      var jsx = [
        '(function(){',
        '  function __esc(s){',
        '    try { return String(s).replace(/\\\\/g,"\\\\\\\\").replace(/\\r?\\n/g,"\\\\n").replace(/"/g,"\\\\\\""); }',
        '    catch(_) { return String(s); }',
        '  }',
        '  try {',
        '    var __code = ' + j(String(code)) + ';',
        '    var __result = eval(__code);',
        '    if (typeof __result === "undefined") __result = "OK";',
        '    return "JSX_OK:" + __esc(__result);',
        '  } catch(e) {',
        '    var __msg  = (e && e.message)   ? e.message   : String(e);',
        '    var __file = (e && e.fileName)  ? e.fileName  : "";',
        '    var __line = (e && (e.line || e.lineNumber)) ? (e.line || e.lineNumber) : "";',
        '    var __stk  = (typeof $ !== "undefined" && $.stack) ? $.stack : "";',
        '    return "JSX_ERR:" + __esc(__msg) + "||" + __esc(__file) + "||" + __esc(__line) + "||" + __esc(__stk);',
        '  }',
        '})();'
      ].join('');

      cs.evalScript(jsx, function (ret) {
        ret = String(ret == null ? '' : ret);

        function deesc(s) {
          try {
            return String(s)
              .replace(/\\n/g, '\n')
              .replace(/\\"/g, '"')
              .replace(/\\\\/g, '\\');
          } catch (_) { return s; }
        }

        if (ret.indexOf('JSX_ERR:') === 0) {
          var parts = ret.slice(8).split('||');
          var msg  = deesc(parts[0] || 'Unknown error');
          var file = deesc(parts[1] || '');
          var line = deesc(parts[2] || '');
          var stk  = deesc(parts[3] || '');

          var human = 'Ошибка в ExtendScript:\n' + msg
            + (file ? ('\nФайл: ' + file) : '')
            + (line ? ('\nСтрока: ' + line) : '')
            + (stk  ? ('\n\nСтек:\n' + stk) : '');

          try { alert(human); } catch (_) {}
          logJSX('[JSX ERROR] ' + human.replace(/\\n/g, ' | '));
          return;
        }

        if (ret.indexOf('JSX_OK:') === 0) {
          logJSX('[eval OK] ' + deesc(ret.slice(7)));
        } else {
          logJSX('[eval RAW] ' + deesc(ret));
        }
      });
    }

    // ========================================================================
    // SAFE eval for CEP JavaScript — moved from app.js
    // ========================================================================
    function evalJS_Safe(code) {
      return new Promise(function (resolve) {
        var logs = [];

        var toStr = function (v) {
          try {
            if (typeof v === 'string') return v;
            if (typeof v === 'function') return v.toString();
            var seen = new WeakSet();
            return JSON.stringify(v, function (k, val) {
              if (typeof val === 'object' && val) { if (seen.has(val)) return '[Circular]'; seen.add(val); }
              return val;
            });
          } catch (_) { try { return String(v); } catch (__){ return Object.prototype.toString.call(v); } }
        };

        var formatError = function (e) {
          try {
            var name = e && e.name ? e.name : '';
            var msg  = e && e.message ? e.message : String(e);
            var file = (e && (e.fileName || e.sourceURL)) || '';
            var line = (e && (e.line || e.lineNumber)) || '';
            var col  = (e && (e.column || e.columnNumber)) || '';
            var stack= e && e.stack ? String(e.stack) : '';
            return (name ? name + ': ' : '') + msg
              + (file ? ('\nФайл: ' + file) : '')
              + (line ? ('\nСтрока: ' + line + (col ? (', столбец: ' + col) : '')) : '')
              + (stack ? ('\n\nСтек:\n' + stack) : '');
          } catch (_) { return String(e); }
        };

        var push = function (type, args) {
          try { logs.push('[' + type + '] ' + Array.prototype.slice.call(args).map(toStr).join(' ')); }
          catch (e) { logs.push('[log-error] ' + String(e)); }
        };

        var oc = window.console;
        var prox = {
          log:   function(){ push('log',   arguments); oc && oc.log   && oc.log.apply(oc, arguments); },
          warn:  function(){ push('warn',  arguments); oc && oc.warn  && oc.warn.apply(oc, arguments); },
          error: function(){ push('error', arguments); oc && oc.error && oc.error.apply(oc, arguments); },
          info:  function(){ push('info',  arguments); oc && oc.info  && oc.info.apply(oc, arguments); },
          debug: function(){ push('debug', arguments); oc && oc.debug && oc.debug.apply(oc, arguments); }
        };
        for (var k in oc) { if (!(k in prox)) { try { prox[k] = typeof oc[k] === 'function' ? oc[k].bind(oc) : oc[k]; } catch (_) {} } }

        function normalize(str) {
          try {
            return String(str == null ? '' : str)
              .replace(/\uFEFF/g, '')                       // BOM
              .replace(/[\u2028\u2029]/g, '\n')           // line/para separators
              .replace(/\u00A0/g, ' ')                      // nbsp
              .replace(/\r\n?|\n/g, '\n');               // CRLF→LF
          } catch (_) { return String(str); }
        }

        code = normalize(code);

        // Feature detect async support in this engine (CEP Chromium varies by app/version)
        var supportsAsync = true;
        try { new Function('async function __a__(){}'); } catch (e) { supportsAsync = false; }

        var runner, isAsync = false;
        try {
          if (supportsAsync && /(\W|^)await(\W|$)/.test(code)) {
            // Wrap into async IIFE if user code uses await
            runner = new Function('(async function(){ "use strict";\n' + code + '\n}).call(this)');
            isAsync = true;
          } else {
            runner = new Function('"use strict";\n' + code);
          }
        } catch (compileErr) {
          return resolve({ ok:false, error: formatError(compileErr), logs: logs });
        }

        window.console = prox;
        try {
          var res = runner.call(window);
          var finalize = function(ok, val) {
            window.console = oc;
            if (ok) resolve({ ok:true, result: val, logs: logs });
            else    resolve({ ok:false, error: formatError(val), logs: logs });
          };
          if (isAsync && res && typeof res.then === 'function') {
            res.then(function(v){ finalize(true, v); }, function(err){ finalize(false, err); });
          } else {
            finalize(true, res);
          }
        } catch (err) {
          window.console = oc;
          resolve({ ok:false, error: formatError(err), logs: logs });
        }
      });
    }

    // ========================================================================
    // Bind UI for both editors
    // ========================================================================
    function bindEditorsUI() {
      // JSX editor
      $runJsxCode.on('click', function () {
        var code = String($jsxEditor.val() || '').trim();
        if (!code) return alert('Введите код ExtendScript');
        evalScript_Safe(code);
      });
      $jsxEditor.on('keydown', function (e) {
        if ((e.ctrlKey || e.metaKey) && e.keyCode === 13) { e.preventDefault(); $runJsxCode.click(); }
      });

      // JS editor
      $runJsCode.on('click', function () {
        var code = String($jsEditor.val() || '').trim();
        if (!code) return alert('Введите JS код');
        logJSExec('— — — запуск — — —');
        evalJS_Safe(code).then(function (out) {
          (out.logs || []).forEach(function (line) { logJSExec(line); });
          if (out.ok) {
            try {
              var resStr = (typeof out.result === 'string') ? out.result : JSON.stringify(out.result, null, 2);
              logJSExec('[eval OK] ' + (typeof resStr === 'undefined' ? 'undefined' : resStr));
            } catch (_) {
              logJSExec('[eval OK] ' + String(out.result));
            }
          } else {
            logJSExec('[JS ERROR] ' + String(out.error).replace(/\\n/g, ' | '));
            try { alert('Ошибка в JS:\\n' + String(out.error)); } catch (_) {}
          }
        });
      });
      $jsEditor.on('keydown', function (e) {
        if ((e.ctrlKey || e.metaKey) && e.keyCode === 13) { e.preventDefault(); $runJsCode.click(); }
      });
    }

    bindEditorsUI();
    logJS('[Editors] редакторы подключены.');
  }

  window.Editors = {setupEditors};
  
})(window);
