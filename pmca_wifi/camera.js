/* ES5 for the original Sony camera WebView. Commands are fixed and scoped. */
(function () {
    'use strict';
    var c = window.CFG, rt, busy = false, status = document.getElementById('status');
    var button = document.getElementById('install');
    function say(text) { status.innerHTML = ''; status.appendChild(document.createTextNode(text)); }
    function report(kind, data, next) {
        var x = new XMLHttpRequest();
        x.open('GET', c.prefix + '/report?event=' + encodeURIComponent(kind) + '&data=' + encodeURIComponent(JSON.stringify(data)) + '&t=' + new Date().getTime(), true);
        x.onreadystatechange = function () {
            if (x.readyState === 4 && next) { var done = next; next = null; done(x.status === 200); }
        };
        x.send(null);
    }
    function run(args) {
        var p = rt.exec(args), code = p.waitFor(), streams = [p.getInputStream(), p.getErrorStream()], result = [];
        for (var k = 0; k < streams.length; k++) {
            var stream = streams[k], text = '', value;
            while (stream.available() > 0 && text.length < 4096) {
                value = stream.read(); if (value < 0) { break; } text += String.fromCharCode(value);
            }
            stream.close(); result.push(text);
        }
        return {code: code, output: result[0], error: result[1]};
    }
    function clean() {
        var p = c.target;
        var r = run(['/system/bin/sh', '-c', 'if [ -e ' + p + ' ]; then rm ' + p + '; fi; if [ -e ' + p + ' ]; then exit 1; fi']);
        return r.code === 0;
    }
    function installedMd5() {
        var r = run(['/system/bin/pm', 'path', c.package]);
        var path = r.output.replace(/^package:/, '').replace(/\s+$/, '');
        if (r.code !== 0 || !/^\/data\/app\/[A-Za-z0-9_.\/-]+\.apk$/.test(path)) { return ''; }
        var hash = run(['/system/bin/md5', path]);
        var match = hash.output.toLowerCase().match(/[0-9a-f]{32}/);
        return hash.code === 0 && match ? match[0] : '';
    }
    function done(already) {
        if (!clean()) { throw new Error('Temporary package cleanup failed. Keep this page open.'); }
        button.style.display = 'none';
        say(already ? 'This version is already installed. Transfer checked. You can close this page.' : 'Installation verified. You can close this page.');
        report('verified', {md5: c.apkMd5, cleaned: true, alreadyInstalled: already});
    }
    function fail(error) {
        busy = false;
        say(String(error));
        var cleaned = false;
        try { if (rt) { cleaned = clean(); } } catch (ignored) {}
        report('error', {message: String(error).substr(0, 300), cleaned: cleaned});
        button.style.display = 'block'; button.disabled = false; button.innerHTML = 'Try again';
    }
    function launch(already) {
        report('prepared', {md5: c.spkMd5}, function (ok) {
            if (!ok) { fail(new Error('Computer did not confirm the checked package.')); return; }
            try {
                if (already) { done(true); return; }
                say('Opening Sony installer. Confirm on camera. After installation, reopen PlayMemories to finish.');
                report('opening', {}, function (accepted) {
                    if (!accepted) { fail(new Error('Computer did not confirm installer launch.')); return; }
                    try {
                        var r = run(['/system/bin/am', 'start', '-a', 'android.intent.action.VIEW', '-d', 'file://' + c.target, '-t', 'application/vnd.android.package-archive']);
                        if (r.code !== 0 || /Error:|Exception/.test(r.output + r.error)) { throw new Error('Sony installer could not start.'); }
                    } catch (e) { fail(e); }
                });
            } catch (e) { fail(e); }
        });
    }
    function write(data, already) {
        say('Preparing package on camera. Please wait...');
        var process = rt.exec(['/system/bin/sh', '-c', 'cat > ' + c.target + ' && chmod 644 ' + c.target + ' && /system/bin/md5 ' + c.target]);
        var output = process.getOutputStream();
        try {
            for (var pos = 0; pos < data.length; pos += 8192) {
                var count = Math.min(8192, data.length - pos), chunk = [];
                for (var n = 0; n < count; n++) { var b = data[pos + n]; chunk.push(b > 127 ? b - 256 : b); }
                output.write(chunk, 0, count);
            }
            output.flush();
        } finally { output.close(); }
        var code = process.waitFor(), stream = process.getInputStream(), text = '', value;
        while (stream.available() > 0 && text.length < 1024) { value = stream.read(); if (value < 0) { break; } text += String.fromCharCode(value); }
        stream.close(); process.getErrorStream().close();
        if (code !== 0 || text.toLowerCase().indexOf(c.spkMd5) < 0) { throw new Error('Camera file checksum did not match.'); }
        launch(already);
    }
    function download(already) {
        say('Receiving app. Keep this page open...');
        var x = new XMLHttpRequest(), finished = false;
        x.open('GET', c.prefix + '/app.spk', true);
        try { x.responseType = 'arraybuffer'; } catch (ignored) {}
        var binary = x.responseType === 'arraybuffer';
        if (!binary && x.overrideMimeType) { x.overrideMimeType('text/plain; charset=x-user-defined'); }
        x.onreadystatechange = function () {
            if (x.readyState !== 4 || finished) { return; } finished = true;
            try {
                if (x.status !== 200) { throw new Error('App download failed.'); }
                var data, i;
                if (binary && x.response) { data = new Uint8Array(x.response); }
                else { var s = x.responseText; data = new Uint8Array(s.length); for (i = 0; i < s.length; i++) { data[i] = s.charCodeAt(i) & 255; } }
                var table = [], crc = -1;
                for (var a = 0; a < 256; a++) { var v = a; for (var k = 0; k < 8; k++) { v = v & 1 ? 0xedb88320 ^ (v >>> 1) : v >>> 1; } table[a] = v; }
                for (i = 0; i < data.length; i++) { crc = (crc >>> 8) ^ table[(crc ^ data[i]) & 255]; }
                if (data.length !== c.size || ((crc ^ -1) >>> 0) !== c.crc32) { throw new Error('Transfer checksum did not match.'); }
                write(data, already);
            } catch (e) { fail(e); }
        };
        x.send(null);
        window.setTimeout(function () { if (!finished) { finished = true; x.abort(); fail(new Error('Download timed out.')); } }, 120000);
    }
    button.onclick = function () {
        if (busy) { return; } busy = true; button.disabled = true;
        try {
            var already = installedMd5() === c.apkMd5;
            report('downloading', {}, function (ok) { if (ok) { download(already); } else { fail(new Error('Computer session expired.')); } });
        } catch (e) { fail(e); }
    };
    try {
        rt = window.searchBoxJavaBridge_.getClass().forName('java.lang.Runtime').getMethod('getRuntime', null).invoke(null, null);
        if (c.phase === 'done') { say('Installation verified. You can close this page.'); return; }
        if (c.phase === 'installing') {
            if (installedMd5() === c.apkMd5) { done(false); return; }
            say('The selected version is not installed yet. If you cancelled, you may close this page or try again.');
            button.innerHTML = 'Try again';
        } else {
            var sdk = parseInt(run(['/system/bin/getprop', 'ro.build.version.sdk']).output, 10);
            if (sdk > 0 && c.minSdk > sdk) { throw new Error('This app requires a newer Android version than this camera.'); }
            say('Ready. Select Install app, then confirm the Sony installer.');
            report('ready', {sdk: sdk || 0});
        }
        button.style.display = 'block';
    } catch (e) { fail(e); button.style.display = 'none'; }
}());
