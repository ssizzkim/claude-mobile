import Cocoa
import WebKit
import Speech
import AVFoundation
import UniformTypeIdentifiers
import CoreGraphics
import SQLite3

let REMOTE_URL = "http://trqdsgn.com/schd/"

// ─── 네이티브 음성인식 핸들러 ────────────────────────────────────────
// 핵심: AVAudioEngine은 한 번만 시작. 세션 교체 시 새 Request를 먼저 열고
// 탭이 즉시 전환된 뒤 이전 Request를 닫는 "핫스왑" 방식으로 끊김 제거.
class NativeSpeechHandler: NSObject, WKScriptMessageHandler {
    weak var webView: WKWebView?
    private let audioEngine = AVAudioEngine()
    private var recRequest: SFSpeechAudioBufferRecognitionRequest?
    private var recTask:    SFSpeechRecognitionTask?
    private let recognizer  = SFSpeechRecognizer(locale: Locale(identifier: "ko-KR"))
    private var active      = false
    private var sessionID   = 0   // 오래된 콜백 무시용 ID

    func userContentController(_ uc: WKUserContentController,
                                didReceive msg: WKScriptMessage) {
        guard msg.name == "nativeSpeech",
              let d = msg.body as? [String: Any],
              let cmd = d["cmd"] as? String else { return }
        DispatchQueue.main.async {
            if cmd == "start" { self.authorize() }
            else if cmd == "stop" { self.fullStop() }
        }
    }

    // ── 권한 확인 (이미 허용이면 팝업 없이 즉시 시작) ──
    private func authorize() {
        if SFSpeechRecognizer.authorizationStatus() == .authorized {
            startEngine(); return
        }
        SFSpeechRecognizer.requestAuthorization { [weak self] st in
            DispatchQueue.main.async {
                if st == .authorized { self?.startEngine() }
                else { self?.js("nativeSpeechError('음성 인식 권한이 필요합니다. 시스템 설정 > 개인정보 보호 및 보안 > 음성 인식에서 앱을 허용해주세요.')") }
            }
        }
    }

    // ── 엔진 시작 (전체 녹음 기간 동안 한 번만) ──
    private func startEngine() {
        guard !audioEngine.isRunning else {
            newSession(isFirst: false); return
        }
        let node = audioEngine.inputNode
        let fmt  = node.outputFormat(forBus: 0)
        // 탭은 한 번만 설치. recRequest가 바뀌면 자동으로 새 req에 전달됨
        node.installTap(onBus: 0, bufferSize: 4096, format: fmt) { [weak self] buf, _ in
            self?.recRequest?.append(buf)
        }
        do {
            audioEngine.prepare()
            try audioEngine.start()
        } catch {
            js("nativeSpeechError('마이크 시작 오류: \(error.localizedDescription)')"); return
        }
        active = true
        newSession(isFirst: true)
        js("nativeSpeechStarted()")
    }

    // ── 세션 핫스왑: 새 req 먼저 열고 → 탭 즉시 전환 → 이전 req 닫기 ──
    private func newSession(isFirst: Bool = false) {
        guard let rec = recognizer, rec.isAvailable, active else { return }

        sessionID += 1
        let myID = sessionID

        // 1) 새 request 생성 & 탭 전환 (이 시점부터 버퍼가 새 req로 들어감)
        let newReq = SFSpeechAudioBufferRecognitionRequest()
        newReq.shouldReportPartialResults = true

        let oldReq  = recRequest
        let oldTask = recTask
        recRequest = newReq   // ← 탭 클로저가 즉시 여기로 전환

        // 2) 새 인식 태스크 시작
        recTask = rec.recognitionTask(with: newReq) { [weak self] result, error in
            guard let self = self, self.active, self.sessionID == myID else { return }

            if let result = result {
                let esc = result.bestTranscription.formattedString
                    .replacingOccurrences(of: "\\", with: "\\\\")
                    .replacingOccurrences(of: "'",  with: "\\'")
                let fin = result.isFinal
                DispatchQueue.main.async {
                    self.js("nativeSpeechResult('\(esc)', \(fin))")
                    if fin { self.newSession() }   // 세션 끝 → 즉시 핫스왑
                }
            }
            if let err = error as NSError?, self.active {
                let normalEnd = [203, 209, 216, 301]
                if !normalEnd.contains(err.code) {
                    DispatchQueue.main.asyncAfter(deadline: .now() + 0.2) {
                        if self.active, self.sessionID == myID { self.newSession() }
                    }
                }
            }
        }

        // 3) 이전 세션은 새 세션이 준비된 후에 종료 (첫 세션이면 없음)
        if !isFirst {
            oldTask?.cancel()
            oldReq?.endAudio()
        }
    }

    // ── 완전 중지 ──
    private func fullStop() {
        active   = false
        sessionID += 1          // 진행 중인 콜백 전부 무시
        recTask?.cancel();    recTask   = nil
        recRequest?.endAudio(); recRequest = nil
        if audioEngine.isRunning {
            audioEngine.stop()
            audioEngine.inputNode.removeTap(onBus: 0)
        }
        js("nativeSpeechStopped()")
    }

    private func js(_ code: String) {
        webView?.evaluateJavaScript(code, completionHandler: nil)
    }
}

// ─── 백업 다운로드 핸들러 (Swift URLSession.shared → NSSavePanel) ─────────
class BackupDownloadHandler: NSObject, WKScriptMessageHandler {
    weak var webView: WKWebView?
    // task를 프로퍼티로 유지 — 로컬 session이 ARC로 해제되는 버그 방지
    private var task: URLSessionDataTask?

    func userContentController(_ uc: WKUserContentController,
                                didReceive msg: WKScriptMessage) {
        guard msg.name == "requestBackup" else { return }
        DispatchQueue.main.async { [weak self] in self?.startBackup() }
    }

    private func startBackup() {
        js("_backupStep('쿠키 확인 중...')")

        WKWebsiteDataStore.default().httpCookieStore.getAllCookies { [weak self] cookies in
            guard let self = self else { return }

            // 쿠키 도메인 필터 (leading dot 포함)
            let cookieHeader = cookies
                .filter { $0.domain.contains("trqdsgn") }
                .map { "\($0.name)=\($0.value)" }
                .joined(separator: "; ")

            DispatchQueue.main.async {
                self.js("_backupStep('요청 중... (쿠키 \(cookies.count)개)')")
            }

            guard let url = URL(string: "http://trqdsgn.com/schd/api.php?action=backup") else { return }
            var request = URLRequest(url: url)
            request.httpMethod = "GET"
            request.timeoutInterval = 120
            if !cookieHeader.isEmpty {
                request.setValue(cookieHeader, forHTTPHeaderField: "Cookie")
            }

            // URLSession.shared — 프로퍼티로 task 유지해 ARC 해제 방지
            self.task = URLSession.shared.dataTask(with: request) { [weak self] data, response, error in
                guard let self = self else { return }
                self.task = nil

                if let error = error {
                    let m = error.localizedDescription.replacingOccurrences(of: "'", with: "\\'")
                    DispatchQueue.main.async { self.js("backupSaveError('\(m)')") }
                    return
                }
                guard let http = response as? HTTPURLResponse else {
                    DispatchQueue.main.async { self.js("backupSaveError('응답 없음')") }
                    return
                }
                guard http.statusCode == 200, let data = data, data.count > 100 else {
                    // 응답 앞부분을 에러 메시지로 포함 (서버 JSON 에러 파악)
                    let preview = data.flatMap { String(data: $0.prefix(120), encoding: .utf8) } ?? ""
                    let safe = preview.replacingOccurrences(of: "'", with: "\"")
                    DispatchQueue.main.async {
                        self.js("backupSaveError('HTTP \(http.statusCode): \(safe)')")
                    }
                    return
                }
                DispatchQueue.main.async {
                    self.js("_backupStep('저장 위치 선택...')")
                    self.saveFile(data: data)
                }
            }
            self.task?.resume()
        }
    }

    private func saveFile(data: Data) {
        let d = Date()
        let cal = Calendar.current
        let stamp = String(format: "%04d%02d%02d",
            cal.component(.year, from: d),
            cal.component(.month, from: d),
            cal.component(.day, from: d))

        let panel = NSSavePanel()
        panel.nameFieldStringValue = "TORQUE_backup_\(stamp).zip"
        if let zipType = UTType(filenameExtension: "zip") {
            panel.allowedContentTypes = [zipType]
        }
        panel.canCreateDirectories = true
        panel.begin { [weak self] response in
            guard response == .OK, let url = panel.url else {
                DispatchQueue.main.async { self?.js("backupSaveError('취소됨')") }
                return
            }
            do {
                try data.write(to: url)
                DispatchQueue.main.async { self?.js("backupSaveComplete()") }
            } catch {
                let m = error.localizedDescription.replacingOccurrences(of: "'", with: "\\'")
                DispatchQueue.main.async { self?.js("backupSaveError('\(m)')") }
            }
        }
    }

    private func js(_ code: String) {
        DispatchQueue.main.async { [weak self] in
            self?.webView?.evaluateJavaScript(code, completionHandler: nil)
        }
    }
}

// ─── (레거시) JS base64 → NSSavePanel (사용 안 함, 호환성 유지) ─────────
class DownloadFileHandler: NSObject, WKScriptMessageHandler {
    weak var webView: WKWebView?
    // JS(nativeSaveBase64)가 넘긴 base64를 NSSavePanel로 저장.
    // WKWebView는 <a download>(blob:/data:)를 받지 못하므로 앱에서는 이 브리지를 쓴다.
    func userContentController(_ uc: WKUserContentController, didReceive msg: WKScriptMessage) {
        guard msg.name == "downloadFile",
              let body = msg.body as? [String: Any],
              let b64 = body["base64"] as? String,
              let data = Data(base64Encoded: b64, options: .ignoreUnknownCharacters) else { return }
        let rawName = (body["filename"] as? String) ?? ""
        let filename = rawName.isEmpty ? "download" : rawName
        DispatchQueue.main.async { [weak self] in
            let panel = NSSavePanel()
            panel.nameFieldStringValue = filename
            if let ext = filename.components(separatedBy: ".").last, ext != filename, ext.count < 8,
               let ut = UTType(filenameExtension: ext.lowercased()) {
                panel.allowedContentTypes = [ut]
            }
            let done: (NSApplication.ModalResponse) -> Void = { resp in
                if resp == .OK, let url = panel.url { try? data.write(to: url) }
            }
            if let win = self?.webView?.window {
                panel.beginSheetModal(for: win, completionHandler: done)
            } else {
                panel.begin(completionHandler: done)
            }
        }
    }
}

// ─── MS To Do 가져오기 핸들러 (로컬 SQLite 읽기 전용 → JS) ─────────────
// JS(todoImportStart)가 요청하면 투두 로컬 DB에서 미완료 할일을 읽어
// base64 JSON으로 receiveTodoTasks()에 전달한다. 투두 데이터는 수정하지 않음.
class TodoImportHandler: NSObject, WKScriptMessageHandler {
    weak var webView: WKWebView?
    func userContentController(_ uc: WKUserContentController, didReceive msg: WKScriptMessage) {
        guard msg.name == "todoImport" else { return }
        DispatchQueue.global(qos: .userInitiated).async { [weak self] in
            let path = NSHomeDirectory() + "/Library/Group Containers/UBF8T346G9.com.microsoft.to-do-mac/AccountData/userdatabase.db"
            var rows: [[String: Any]] = []
            var err = ""
            var db: OpaquePointer?
            if sqlite3_open_v2(path, &db, SQLITE_OPEN_READONLY, nil) == SQLITE_OK {
                let sql = "SELECT tf.name, IFNULL(t.subject,''), IFNULL(t.body_content,''), IFNULL(t.due_date,''), t.importance " +
                          "FROM tasks t JOIN task_folders tf ON t.task_folder_local_id = tf.local_id " +
                          "WHERE t.deleted = 0 AND t.status <> 'Completed' AND tf.deleted = 0"
                var st: OpaquePointer?
                if sqlite3_prepare_v2(db, sql, -1, &st, nil) == SQLITE_OK {
                    while sqlite3_step(st) == SQLITE_ROW {
                        func col(_ i: Int32) -> String {
                            sqlite3_column_text(st, i).map { String(cString: $0) } ?? ""
                        }
                        rows.append(["folder": col(0), "title": col(1), "body": col(2),
                                     "due": col(3), "importance": Int(sqlite3_column_int(st, 4))])
                    }
                    sqlite3_finalize(st)
                } else { err = "query_failed" }
                sqlite3_close(db)
            } else { err = "db_open_failed" }
            let payload: [String: Any] = ["ok": err.isEmpty, "error": err, "rows": rows]
            guard let data = try? JSONSerialization.data(withJSONObject: payload) else { return }
            let b64 = data.base64EncodedString()
            DispatchQueue.main.async {
                self?.webView?.evaluateJavaScript(
                    "if (typeof receiveTodoTasks === 'function') receiveTodoTasks('\(b64)')",
                    completionHandler: nil)
            }
        }
    }
}

// ─── 자동화 도구 핸들러 (신한은행·홈택스·지메일 정리·오늘 정리) ─────────
// JS(bankToolRun)가 요청하면 BankSort 엔진(~/Library/Application Support/BankSort)의
// tools_cli.py 를 실행하고 결과 JSON 을 base64 로 receiveBankTool()에 넘긴다.
// 비밀번호는 표준입력으로만 넘기고 저장하지 않는다.
class BankToolsHandler: NSObject, WKScriptMessageHandler {
    weak var webView: WKWebView?
    func userContentController(_ uc: WKUserContentController, didReceive msg: WKScriptMessage) {
        guard msg.name == "bankTools", let body = msg.body as? [String: Any],
              let action = body["action"] as? String else { return }
        if action == "shinhan" {   // 신한 기업뱅킹 로그인은 맥 크롬에서 안 되고 사파리에서 된다
            let url = URL(string: "https://bizbank.shinhan.com/")!
            if let safari = NSWorkspace.shared.urlForApplication(withBundleIdentifier: "com.apple.Safari") {
                NSWorkspace.shared.open([url], withApplicationAt: safari, configuration: NSWorkspace.OpenConfiguration())
            } else { NSWorkspace.shared.open(url) }
            return
        }
        let input = (body["input"] as? String) ?? ""
        DispatchQueue.global(qos: .userInitiated).async { [weak self] in
            let home = NSHomeDirectory() + "/Library/Application Support/BankSort"
            // 오늘 정리: 카톡은 앱이 직접 읽어 파일로 넘긴다(손쉬운 사용 권한이 앱에 있으므로)
            var kakaoFile = ""
            if action == "daily" {
                let k = KakaoReader.readToday()
                kakaoFile = home + "/kakao_today.json"
                if let d = try? JSONSerialization.data(withJSONObject: k) { try? d.write(to: URL(fileURLWithPath: kakaoFile)) }
            }
            let p = Process()
            p.executableURL = URL(fileURLWithPath: home + "/venv/bin/python")
            p.arguments = [home + "/tools_cli.py", action]
            p.currentDirectoryURL = URL(fileURLWithPath: home)
            var env = ProcessInfo.processInfo.environment
            env["LANG"] = "ko_KR.UTF-8"; env["PYTHONIOENCODING"] = "utf-8"
            env["PATH"] = "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:" + (env["PATH"] ?? "")
            if !kakaoFile.isEmpty { env["KAKAO_JSON"] = kakaoFile }
            p.environment = env
            let inPipe = Pipe(), outPipe = Pipe()
            p.standardInput = inPipe; p.standardOutput = outPipe; p.standardError = FileHandle.nullDevice
            var out = Data()
            do {
                try p.run()
                inPipe.fileHandleForWriting.write(input.data(using: .utf8) ?? Data())
                try? inPipe.fileHandleForWriting.close()
                out = outPipe.fileHandleForReading.readDataToEndOfFile()
                p.waitUntilExit()
            } catch {
                out = (try? JSONSerialization.data(withJSONObject: ["ok": false, "action": action,
                    "error": "BankSort 엔진을 실행하지 못했습니다: \(error.localizedDescription)"])) ?? Data()
            }
            if out.isEmpty {
                out = (try? JSONSerialization.data(withJSONObject: ["ok": false, "action": action,
                    "error": "엔진이 결과를 돌려주지 않았습니다"])) ?? Data()
            }
            let b64 = out.base64EncodedString()
            DispatchQueue.main.async {
                self?.webView?.evaluateJavaScript(
                    "if (typeof receiveBankTool === 'function') receiveBankTool('\(b64)')", completionHandler: nil)
            }
        }
    }
}

// ─── 복원 파일 선택 핸들러 (NSOpenPanel → JS) ────────────────────────
// JS에서 요청하면 NSOpenPanel을 열어 ZIP/JSON 선택 후
// base64로 인코딩해 receiveRestoreData() JS 함수에 전달한다.
class RestorePickerHandler: NSObject, WKScriptMessageHandler {
    weak var webView: WKWebView?

    func userContentController(_ uc: WKUserContentController,
                                didReceive msg: WKScriptMessage) {
        guard msg.name == "openRestorePicker" else { return }

        DispatchQueue.main.async { [weak self] in
            let panel = NSOpenPanel()
            panel.allowsMultipleSelection = false
            panel.canChooseFiles = true
            panel.canChooseDirectories = false
            // ZIP + JSON 허용
            var types: [UTType] = []
            if let zip  = UTType(filenameExtension: "zip")  { types.append(zip)  }
            if let json = UTType(filenameExtension: "json") { types.append(json) }
            if !types.isEmpty { panel.allowedContentTypes = types }

            panel.begin { response in
                guard response == .OK, let url = panel.url else { return }
                DispatchQueue.global(qos: .userInitiated).async {
                    guard let data = try? Data(contentsOf: url) else { return }
                    let b64 = data.base64EncodedString()
                    let fn  = url.lastPathComponent
                        .replacingOccurrences(of: "\\", with: "\\\\")
                        .replacingOccurrences(of: "'",  with: "\\'")
                    let js  = "if(typeof receiveRestoreData==='function') receiveRestoreData('\(b64)','\(fn)')"
                    DispatchQueue.main.async {
                        self?.webView?.evaluateJavaScript(js, completionHandler: nil)
                    }
                }
            }
        }
    }
}

// ─── PDF 인쇄 핸들러: JS → HTML 전달 → loadHTMLString → createPDF → NSSavePanel ───
class PrintHTMLHandler: NSObject, WKScriptMessageHandler {
    weak var mainWindow: NSWindow?

    func userContentController(_ uc: WKUserContentController,
                                didReceive msg: WKScriptMessage) {
        guard msg.name == "printHTML",
              let body = msg.body as? [String: Any],
              let html = body["html"] as? String else { return }
        let filename = (body["filename"] as? String) ?? "document"
        DispatchQueue.main.async { [weak self] in
            PrintJob.start(html: html, filename: filename, parentWindow: self?.mainWindow)
        }
    }
}

// PrintJob: 화면 밖 WKWebView로 HTML 렌더링 후 createPDF
// .pb(페이지 나누기)가 있는 가로(A4 landscape) 문서(=견적서)는 블록(공종)별로 createPDF한 뒤
// 물리 A4 페이지로 합성한다. createPDF는 @page·page-break를 무시해 한 장으로 길게 나오므로,
// 각 블록을 A4 크기 박스로 강제하고 px→pt(0.75) 벡터 스케일로 합쳐 공종 분할 + 균일 선두께를 얻는다.
class PrintJob: NSObject, WKNavigationDelegate {
    private var webView: WKWebView!
    private let html: String
    private let filename: String
    private weak var parentWindow: NSWindow?
    private static var active: [PrintJob] = []  // ARC 방지용 강참조

    // 페이지 분할(벡터 합성) 모드 파라미터
    private let paginate: Bool
    private let isLandscape: Bool
    private let marginMm: Int
    private let pageWpx: CGFloat
    private let pageHpx: CGFloat
    private let ptW: CGFloat
    private let ptH: CGFloat
    private var blockTops: [CGFloat] = []
    private var pageDatas: [Data] = []
    private var idx = 0

    static func start(html: String, filename: String, parentWindow: NSWindow?) {
        let job = PrintJob(html: html, filename: filename, parentWindow: parentWindow)
        active.append(job)
        job.run()
    }

    private init(html: String, filename: String, parentWindow: NSWindow?) {
        self.html = html
        self.filename = filename
        self.parentWindow = parentWindow
        let hasPb = html.range(of: "class=\"pb\"") != nil || html.range(of: "class='pb'") != nil
        let landscape = html.range(of: "@page[^}]*landscape", options: .regularExpression) != nil
        // 가로 + .pb 인 문서(견적서)만 분할. 세로 계약서 등은 기존 동작 유지(클리핑 위험 회피).
        self.paginate = hasPb && landscape
        self.isLandscape = landscape
        // @page margin(mm) 파싱
        var mm = 10
        if let re = try? NSRegularExpression(pattern: "@page[^}]*margin\\s*:\\s*([0-9.]+)\\s*mm"),
           let m = re.firstMatch(in: html, range: NSRange(html.startIndex..., in: html)),
           let r = Range(m.range(at: 1), in: html), let v = Double(html[r]) {
            mm = Int(v.rounded())
        }
        self.marginMm = mm
        let PXMM: CGFloat = 96.0 / 25.4            // px per mm @96dpi
        let longPx = 297 * PXMM, shortPx = 210 * PXMM
        self.pageWpx = landscape ? longPx : shortPx
        self.pageHpx = landscape ? shortPx : longPx
        let SCALE: CGFloat = 72.0 / 96.0           // px(96dpi) -> pt(72dpi)
        self.ptW = pageWpx * SCALE
        self.ptH = pageHpx * SCALE
        super.init()
    }

    private func run() {
        let cfg = WKWebViewConfiguration()
        cfg.websiteDataStore = WKWebsiteDataStore.nonPersistent()
        let w: CGFloat = paginate ? pageWpx : 900
        let h: CGFloat = paginate ? 30000 : 1200
        webView = WKWebView(frame: NSRect(x: 0, y: 0, width: w, height: h), configuration: cfg)
        webView.navigationDelegate = self
        webView.loadHTMLString(html, baseURL: nil)
    }

    func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) {
        if paginate { startPaginated(); return }
        // ── 기존 단순 모드(흐름형 문서) ──
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.6) { [weak self] in
            guard let self = self else { return }
            self.webView.createPDF { result in
                DispatchQueue.main.async {
                    guard case .success(let data) = result else {
                        PrintJob.active.removeAll { $0 === self }; return
                    }
                    self.presentSave(data: data)
                }
            }
        }
    }

    // ── 페이지 분할(벡터 합성) 모드 ──
    private func startPaginated() {
        let wmm = isLandscape ? 297 : 210
        let hmm = isLandscape ? 210 : 297
        // 각 최상위 블록을 A4 박스로 강제(인쇄 레이아웃과 동일), body 여백은 0으로 덮어쓰기.
        let css = "var s=document.createElement('style');"
            + "s.textContent='html,body{margin:0!important;padding:0!important;background:#fff!important;}"
            + "body>div{width:\(wmm)mm!important;height:\(hmm)mm!important;box-sizing:border-box!important;"
            + "padding:\(marginMm)mm!important;margin:0!important;overflow:hidden!important;}';"
            + "document.head.appendChild(s);"
        webView.evaluateJavaScript(css) { [weak self] _, _ in
            guard let self = self else { return }
            DispatchQueue.main.asyncAfter(deadline: .now() + 0.8) {
                let js = "JSON.stringify(Array.from(document.body.children).filter(e=>e.offsetHeight>0).map(e=>e.offsetTop))"
                self.webView.evaluateJavaScript(js) { res, _ in
                    if let s = res as? String, let d = s.data(using: .utf8),
                       let arr = try? JSONSerialization.jsonObject(with: d) as? [Double], !arr.isEmpty {
                        self.blockTops = arr.map { CGFloat($0) }
                        self.renderNextBlock()
                    } else {
                        self.fallbackSinglePDF()   // 측정 실패 → 안전 폴백
                    }
                }
            }
        }
    }

    private func renderNextBlock() {
        if idx >= blockTops.count { finishPaginated(); return }
        let top = blockTops[idx]
        let cfg = WKPDFConfiguration()
        cfg.rect = CGRect(x: 0, y: top, width: pageWpx, height: pageHpx)
        webView.createPDF(configuration: cfg) { [weak self] result in
            guard let self = self else { return }
            if case .success(let data) = result { self.pageDatas.append(data) }
            self.idx += 1
            DispatchQueue.main.async { self.renderNextBlock() }
        }
    }

    private func finishPaginated() {
        if pageDatas.isEmpty { fallbackSinglePDF(); return }
        let pdfData = NSMutableData()
        var mediaBox = CGRect(x: 0, y: 0, width: ptW, height: ptH)
        guard let consumer = CGDataConsumer(data: pdfData as CFMutableData),
              let ctx = CGContext(consumer: consumer, mediaBox: &mediaBox, nil) else {
            PrintJob.active.removeAll { $0 === self }; return
        }
        let target = CGRect(x: 0, y: 0, width: ptW, height: ptH)
        for data in pageDatas {
            guard let prov = CGDataProvider(data: data as CFData),
                  let doc = CGPDFDocument(prov), let pg = doc.page(at: 1) else { continue }
            // 캡처된 px 크기 페이지를 물리 A4(pt)에 맞춰 변환(원점 보정 + 0.75 스케일 자동 처리)
            let tf = pg.getDrawingTransform(.mediaBox, rect: target, rotate: 0, preserveAspectRatio: true)
            ctx.beginPDFPage(nil)
            ctx.saveGState()
            ctx.concatenate(tf)
            ctx.clip(to: pg.getBoxRect(.mediaBox))
            ctx.drawPDFPage(pg)
            ctx.restoreGState()
            ctx.endPDFPage()
        }
        ctx.closePDF()
        if pdfData.length > 0 { presentSave(data: pdfData as Data) }
        else { PrintJob.active.removeAll { $0 === self } }
    }

    private func fallbackSinglePDF() {
        webView.createPDF { [weak self] result in
            DispatchQueue.main.async {
                guard let self = self else { return }
                if case .success(let data) = result { self.presentSave(data: data) }
                else { PrintJob.active.removeAll { $0 === self } }
            }
        }
    }

    private func presentSave(data: Data) {
        let pdfName = filename.hasSuffix(".pdf") ? filename : filename + ".pdf"
        let panel = NSSavePanel()
        panel.allowedContentTypes  = [.pdf]
        panel.nameFieldStringValue = pdfName
        let done: (NSApplication.ModalResponse) -> Void = { [weak self] response in
            if response == .OK, let url = panel.url { try? data.write(to: url) }
            if let self = self { PrintJob.active.removeAll { $0 === self } }
        }
        if let win = parentWindow {
            panel.beginSheetModal(for: win, completionHandler: done)
        } else {
            panel.begin(completionHandler: done)
        }
    }

    func webView(_ webView: WKWebView, didFail navigation: WKNavigation!, withError error: Error) {
        PrintJob.active.removeAll { $0 === self }
    }
}

// ─── 메인 WebView ─────────────────────────────────────────────────
class TorqueWebView: WKWebView, WKUIDelegate, WKNavigationDelegate {
    var isOnline = true
    var printHandler: PrintHTMLHandler?

    // ── 로드 함수: 온라인 → 서버 URL, 실패 → 로컬 폴백 ──
    func loadApp() {
        if let url = URL(string: REMOTE_URL) {
            var req = URLRequest(url: url)
            req.cachePolicy = .reloadIgnoringLocalAndRemoteCacheData
            load(req)
        }
    }

    // 서버 로드 성공
    func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) {
        isOnline = true
        updateTitle(online: true)
    }

    // 진짜 앱 페이지(http/https) 로드 실패일 때만 폴백.
    // 다운로드(<a download>의 blob:/data:)나 정책 취소(-999, WebKitErrorDomain)로 생기는
    // 실패에서 폴백하면 서버 데이터가 "초기화"된 것처럼 보이는 사고가 난다.
    private func shouldFallback(onError error: Error) -> Bool {
        let e = error as NSError
        if e.domain != NSURLErrorDomain { return false }
        if e.code == NSURLErrorCancelled { return false }
        let failing = (e.userInfo[NSURLErrorFailingURLErrorKey] as? URL)
            ?? (e.userInfo[NSURLErrorFailingURLStringErrorKey] as? String).flatMap { URL(string: $0) }
        if let scheme = failing?.scheme?.lowercased(), scheme != "http", scheme != "https" { return false }
        return true
    }

    // 서버 로드 실패 → 로컬 HTML 폴백
    func webView(_ webView: WKWebView,
                 didFailProvisionalNavigation navigation: WKNavigation!,
                 withError error: Error) {
        guard shouldFallback(onError: error) else { return }
        isOnline = false
        updateTitle(online: false)
        loadLocalFallback()
    }

    func webView(_ webView: WKWebView,
                 didFail navigation: WKNavigation!,
                 withError error: Error) {
        // HTTP 로드 중 실패도 처리
        guard shouldFallback(onError: error) else { return }
        isOnline = false
        updateTitle(online: false)
        loadLocalFallback()
    }

    func loadLocalFallback() {
        if let htmlPath = Bundle.main.path(forResource: "index", ofType: "html"),
           let resURL = Bundle.main.resourceURL {
            loadFileURL(URL(fileURLWithPath: htmlPath), allowingReadAccessTo: resURL)
        }
    }

    func updateTitle(online: Bool) {
        DispatchQueue.main.async {
            if let w = self.window {
                w.title = online ? "토르크 관리" : "토르크 관리  ◌  오프라인"
            }
        }
    }

    // ── window.open() 팝업 차단 (printHTML 핸들러 방식으로 대체) ──
    func webView(_ webView: WKWebView,
                 createWebViewWith configuration: WKWebViewConfiguration,
                 for navigationAction: WKNavigationAction,
                 windowFeatures: WKWindowFeatures) -> WKWebView? {
        return nil  // 팝업 무시
    }

    // ── alert / confirm / prompt ──
    func webView(_ webView: WKWebView,
                 runJavaScriptAlertPanelWithMessage message: String,
                 initiatedByFrame frame: WKFrameInfo,
                 completionHandler: @escaping () -> Void) {
        let a = NSAlert()
        a.messageText = message
        a.addButton(withTitle: "확인")
        a.runModal()
        completionHandler()
    }

    func webView(_ webView: WKWebView,
                 runJavaScriptConfirmPanelWithMessage message: String,
                 initiatedByFrame frame: WKFrameInfo,
                 completionHandler: @escaping (Bool) -> Void) {
        let a = NSAlert()
        a.messageText = message
        a.addButton(withTitle: "확인")
        a.addButton(withTitle: "취소")
        completionHandler(a.runModal() == .alertFirstButtonReturn)
    }

    func webView(_ webView: WKWebView,
                 runJavaScriptTextInputPanelWithPrompt prompt: String,
                 defaultText: String?,
                 initiatedByFrame frame: WKFrameInfo,
                 completionHandler: @escaping (String?) -> Void) {
        let a = NSAlert()
        a.messageText = prompt
        a.addButton(withTitle: "확인")
        a.addButton(withTitle: "취소")
        let field = NSTextField(frame: NSRect(x:0,y:0,width:320,height:24))
        field.stringValue = defaultText ?? ""
        a.accessoryView = field
        a.window.initialFirstResponder = field
        completionHandler(a.runModal() == .alertFirstButtonReturn ? field.stringValue : nil)
    }

    // ── 파일 선택 패널 (<input type="file">) ──
    // http:// 페이지에서 file:// 읽기는 cross-origin 제한에 걸리므로
    // Swift에서 직접 NSImage로 읽고 JPEG base64로 변환 후 JS에 주입한다.
    func webView(_ webView: WKWebView,
                 runOpenPanelWith parameters: WKOpenPanelParameters,
                 initiatedByFrame frame: WKFrameInfo,
                 completionHandler: @escaping ([URL]?) -> Void) {
        let panel = NSOpenPanel()
        panel.allowsMultipleSelection = parameters.allowsMultipleSelection
        panel.canChooseFiles = true
        panel.canChooseDirectories = false
        // 이미지 + 문서(hwp·docx·pdf 등) 모두 선택 가능 (형식 제한 없음)
        panel.begin { [weak webView] response in
            guard response == .OK else { completionHandler(nil); return }
            let urls = panel.urls
            func isImage(_ u: URL) -> Bool {
                if let t = try? u.resourceValues(forKeys: [.contentTypeKey]).contentType {
                    return t.conforms(to: .image)
                }
                return ["jpg","jpeg","png","gif","webp","heic","heif","bmp","tiff"].contains(u.pathExtension.lowercased())
            }
            let images = urls.filter(isImage)
            let docs   = urls.filter { !isImage($0) }
            func jsLiteral(_ s: String) -> String {
                if let d = try? JSONSerialization.data(withJSONObject: [s]),
                   let j = String(data: d, encoding: .utf8) {
                    return String(j.dropFirst().dropLast())   // ["x"] → "x"
                }
                return "\"\""
            }
            // 이 WKWebView에선 completionHandler(urls)로 input.files 가 안 채워져 onchange 가 안 뜬다.
            // 그래서 표준 메커니즘은 쓰지 않고, Swift에서 파일을 직접 읽어 JS로 주입한다.
            completionHandler(nil)
            guard let wv = webView else { return }
            DispatchQueue.global(qos: .userInitiated).async {
                // 1) 문서(비이미지): 원본 base64 → docInjectFile → JS가 서버 업로드
                for url in docs {
                    guard let data = try? Data(contentsOf: url) else { continue }
                    var mime = "application/octet-stream"
                    if let ct = try? url.resourceValues(forKeys: [.contentTypeKey]).contentType,
                       let pm = ct.preferredMIMEType { mime = pm }
                    let dataURL = "data:\(mime);base64,\(data.base64EncodedString())"
                    let nameJS  = jsLiteral(url.lastPathComponent)
                    let urlJS   = jsLiteral(dataURL)
                    let size    = data.count
                    DispatchQueue.main.async {
                        wv.evaluateJavaScript("if(typeof docInjectFile==='function') docInjectFile(\(nameJS), \(urlJS), \(size))", completionHandler: nil)
                    }
                }
                // 2) 이미지: 1200px 리사이즈 후 주입 (열린 모달에 맞춰 라우팅)
                for url in images {
                    guard let nsImage = NSImage(contentsOf: url) else { continue }

                    // 최대 1200px 리사이즈 (JS와 동일 기준)
                    let maxPx: CGFloat = 1200
                    let orig = nsImage.size
                    let scale = orig.width > maxPx || orig.height > maxPx
                        ? maxPx / max(orig.width, orig.height) : 1.0
                    let target = NSSize(width: round(orig.width * scale),
                                       height: round(orig.height * scale))

                    let resized = NSImage(size: target)
                    resized.lockFocus()
                    NSGraphicsContext.current?.imageInterpolation = .high
                    nsImage.draw(in: NSRect(origin: .zero, size: target),
                                 from: NSRect(origin: .zero, size: orig),
                                 operation: .copy, fraction: 1.0)
                    resized.unlockFocus()

                    guard let tiff   = resized.tiffRepresentation,
                          let bitmap = NSBitmapImageRep(data: tiff),
                          let jpeg   = bitmap.representation(using: .jpeg,
                              properties: [.compressionFactor: NSNumber(value: 0.75)])
                    else { continue }

                    let b64     = jpeg.base64EncodedString()
                    let dataURL = "data:image/jpeg;base64,\(b64)"

                    DispatchQueue.main.async {
                        wv.evaluateJavaScript(
                            "if(typeof slInjectOnePhoto==='function') slInjectOnePhoto('\(dataURL)')",
                            completionHandler: nil
                        )
                    }
                }
            }
        }
    }

    // ── 외부 링크 처리: 동일 도메인은 WKWebView에서, 외부 도메인은 기본 브라우저로 ──
    // 수정: api.php 등 같은 서버 URL을 Safari로 보내지 않도록 도메인 체크
    func webView(_ webView: WKWebView,
                 decidePolicyFor navigationAction: WKNavigationAction,
                 decisionHandler: @escaping (WKNavigationActionPolicy) -> Void) {
        if let url = navigationAction.request.url,
           (url.scheme == "http" || url.scheme == "https"),
           navigationAction.navigationType == .linkActivated {
            let host = url.host ?? ""
            // trqdsgn.com 도메인은 WKWebView 안에서 처리
            let isSameOrigin = host.contains("trqdsgn.com") || host == "localhost" || host == "127.0.0.1"
            if !isSameOrigin {
                NSWorkspace.shared.open(url)
                decisionHandler(.cancel)
                return
            }
        }
        decisionHandler(.allow)
    }
}

// ─── AppDelegate ──────────────────────────────────────────────────
class AppDelegate: NSObject, NSApplicationDelegate, NSWindowDelegate {
    var mainWindow:       NSWindow?
    var webView:          TorqueWebView?
    var speechHandler:    NativeSpeechHandler?
    var downloadHandler:  DownloadFileHandler?
    var backupHandler:    BackupDownloadHandler?
    var restoreHandler:   RestorePickerHandler?

    func applicationDidFinishLaunching(_ n: Notification) {
        // HTTP 캐시만 초기화 (localStorage·쿠키는 유지)
        let cacheTypes: Set<String> = [
            WKWebsiteDataTypeDiskCache,
            WKWebsiteDataTypeMemoryCache
        ]
        WKWebsiteDataStore.default().removeData(ofTypes: cacheTypes, modifiedSince: .distantPast) { }

        setupMenuBar()
        buildWindow()

        // 앱이 전면으로 올 때마다 서버와 재동기화
        NotificationCenter.default.addObserver(
            self,
            selector: #selector(appBecameActive),
            name: NSApplication.didBecomeActiveNotification,
            object: nil
        )
    }

    @objc func appBecameActive() {
        guard let wv = webView, wv.isOnline else { return }
        wv.evaluateJavaScript("if(typeof syncFromServer==='function') syncFromServer();", completionHandler: nil)
    }

    @objc func reloadPage() {
        guard let wv = webView else { return }
        wv.isOnline ? wv.loadApp() : wv.loadLocalFallback()
    }

    func buildWindow() {
        // 이미 생성된 창이 있으면 앞으로만
        if let win = mainWindow { win.makeKeyAndOrderFront(nil); return }


        let screen = NSScreen.main?.visibleFrame ?? NSRect(x:0,y:0,width:1440,height:900)
        let w = min(CGFloat(1440), screen.width  * 0.9)
        let h = min(CGFloat(900),  screen.height * 0.9)
        let x = screen.minX + (screen.width  - w) / 2
        let y = screen.minY + (screen.height - h) / 2

        let win = NSWindow(
            contentRect: NSRect(x:x, y:y, width:w, height:h),
            styleMask: [.titled, .closable, .miniaturizable, .resizable, .fullSizeContentView],
            backing: .buffered,
            defer: false
        )
        win.title = "토르크 관리"
        win.minSize = NSSize(width: 768, height: 600)
        win.setFrameAutosaveName("TorqueMain")
        win.delegate = self

        // 쿠키·세션 유지 (로그인 상태 영속)
        let cfg = WKWebViewConfiguration()
        cfg.websiteDataStore = WKWebsiteDataStore.default()
        cfg.preferences.javaScriptCanOpenWindowsAutomatically = true

        // 네이티브 앱 플래그 — 로그인 건너뜀
        let nativeFlag = WKUserScript(
            source: "window.IS_NATIVE_APP = true;",
            injectionTime: .atDocumentStart,
            forMainFrameOnly: true
        )
        cfg.userContentController.addUserScript(nativeFlag)

        // 네이티브 음성인식 핸들러 등록
        let sh = NativeSpeechHandler()
        cfg.userContentController.add(sh, name: "nativeSpeech")

        // 백업 다운로드 핸들러 등록 (Swift URLSession → NSSavePanel)
        let dh = DownloadFileHandler()
        cfg.userContentController.add(dh, name: "downloadFile")
        let bh = BackupDownloadHandler()
        cfg.userContentController.add(bh, name: "requestBackup")

        // 복원 파일 선택 핸들러 등록 (NSOpenPanel ZIP/JSON → JS)
        let rh = RestorePickerHandler()
        cfg.userContentController.add(rh, name: "openRestorePicker")

        // MS To Do 가져오기 핸들러 등록 (로컬 SQLite 읽기 전용)
        let th = TodoImportHandler()
        cfg.userContentController.add(th, name: "todoImport")

        // 자동화 도구 핸들러 등록 (BankSort 엔진 실행)
        let bt = BankToolsHandler()
        cfg.userContentController.add(bt, name: "bankTools")

        // PDF 인쇄 핸들러 등록 (HTML → loadHTMLString → createPDF → NSSavePanel)
        let ph = PrintHTMLHandler()
        cfg.userContentController.add(ph, name: "printHTML")

        let wv = TorqueWebView(frame: win.contentView!.bounds, configuration: cfg)
        wv.autoresizingMask = [.width, .height]
        wv.uiDelegate = wv
        wv.navigationDelegate = wv

        win.contentView?.addSubview(wv)
        win.makeKeyAndOrderFront(nil)
        wv.loadApp()

        // 핸들러에 webView / window 연결 (wv 생성 후)
        sh.webView = wv
        dh.webView = wv
        bh.webView = wv
        rh.webView = wv
        th.webView = wv
        bt.webView = wv
        ph.mainWindow = win
        wv.printHandler = ph

        // 프로퍼티는 완전히 준비된 뒤에 저장
        self.mainWindow      = win
        self.webView         = wv
        self.speechHandler   = sh
        self.downloadHandler = dh
        self.backupHandler   = bh
        self.restoreHandler  = rh
    }

    // ⌘W → 닫지 않고 숨기기 (WKWebView 파괴 없이 안전하게)
    func windowShouldClose(_ sender: NSWindow) -> Bool {
        sender.orderOut(nil)
        return false   // 실제 닫기(dealloc)는 막음
    }

    func applicationShouldTerminateAfterLastWindowClosed(_ a: NSApplication) -> Bool { false }

    func applicationShouldHandleReopen(_ a: NSApplication, hasVisibleWindows f: Bool) -> Bool {
        mainWindow?.makeKeyAndOrderFront(nil)
        return true
    }

    func setupMenuBar() {
        let menu = NSMenu()

        // ── 앱 메뉴 ──
        let appItem = NSMenuItem()
        menu.addItem(appItem)
        let appMenu = NSMenu(title: "토르크 관리")
        appItem.submenu = appMenu
        appMenu.addItem(NSMenuItem(title: "토르크 관리 정보",
            action: #selector(NSApplication.orderFrontStandardAboutPanel(_:)), keyEquivalent: ""))
        appMenu.addItem(.separator())
        let hide = NSMenuItem(title: "토르크 관리 숨기기",
            action: #selector(NSApplication.hide(_:)), keyEquivalent: "h")
        appMenu.addItem(hide)
        let hideOthers = NSMenuItem(title: "다른 앱 숨기기",
            action: #selector(NSApplication.hideOtherApplications(_:)), keyEquivalent: "h")
        hideOthers.keyEquivalentModifierMask = [.command, .option]
        appMenu.addItem(hideOthers)
        appMenu.addItem(.separator())
        appMenu.addItem(NSMenuItem(title: "토르크 관리 종료",
            action: #selector(NSApplication.terminate(_:)), keyEquivalent: "q"))

        // ── 편집 메뉴 ──
        let editItem = NSMenuItem()
        menu.addItem(editItem)
        let editMenu = NSMenu(title: "편집")
        editItem.submenu = editMenu
        editMenu.addItem(NSMenuItem(title: "실행 취소", action: #selector(UndoManager.undo),           keyEquivalent: "z"))
        editMenu.addItem(NSMenuItem(title: "다시 실행", action: #selector(UndoManager.redo),           keyEquivalent: "Z"))
        editMenu.addItem(.separator())
        editMenu.addItem(NSMenuItem(title: "잘라내기",  action: #selector(NSText.cut(_:)),             keyEquivalent: "x"))
        editMenu.addItem(NSMenuItem(title: "복사",      action: #selector(NSText.copy(_:)),            keyEquivalent: "c"))
        editMenu.addItem(NSMenuItem(title: "붙여넣기",  action: #selector(NSText.paste(_:)),           keyEquivalent: "v"))
        editMenu.addItem(.separator())
        editMenu.addItem(NSMenuItem(title: "전체 선택", action: #selector(NSText.selectAll(_:)),       keyEquivalent: "a"))

        // ── 보기 메뉴 (새로고침) ──
        let viewItem = NSMenuItem()
        menu.addItem(viewItem)
        let viewMenu = NSMenu(title: "보기")
        viewItem.submenu = viewMenu
        let reloadItem = NSMenuItem(title: "새로고침",
            action: #selector(reloadPage), keyEquivalent: "r")
        reloadItem.target = self
        viewMenu.addItem(reloadItem)

        // ── 윈도우 메뉴 ──
        let winItem = NSMenuItem()
        menu.addItem(winItem)
        let winMenu = NSMenu(title: "윈도우")
        winItem.submenu = winMenu
        winMenu.addItem(NSMenuItem(title: "닫기",      action: #selector(NSWindow.performClose(_:)),         keyEquivalent: "w"))
        winMenu.addItem(NSMenuItem(title: "최소화",    action: #selector(NSWindow.miniaturize(_:)),          keyEquivalent: "m"))
        winMenu.addItem(NSMenuItem(title: "확대/축소", action: #selector(NSWindow.zoom(_:)),                 keyEquivalent: ""))
        winMenu.addItem(.separator())
        winMenu.addItem(NSMenuItem(title: "맨 앞으로", action: #selector(NSWindow.makeKeyAndOrderFront(_:)), keyEquivalent: ""))

        NSApp.mainMenu = menu
        NSApp.windowsMenu = winMenu
    }
}

// ─── 진입점 ───────────────────────────────────────────────────────
let app = NSApplication.shared
app.setActivationPolicy(.regular)
let delegate = AppDelegate()
app.delegate = delegate
app.run()
