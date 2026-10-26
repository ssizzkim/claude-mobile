// 카카오톡 맥 앱에서 '오늘' 대화가 있는 방을 접근성으로 열어 읽고 닫는다 → JSON 출력.
// 저장 파일(암호화 DB)은 건드리지 않는다. 방을 열면 그 방의 안 읽은 메시지는 읽음 처리된다.
// 종료 코드 2 = 손쉬운 사용(접근성) 권한 없음.
import Cocoa
import ApplicationServices

let BUNDLE = "com.kakao.KakaoTalkMac"
let MAX_ROOMS = 30
let MAX_SCROLLS = 40      // 방당 위로 스크롤 상한 (아침 대화까지 로드)
let MAX_MSGS = 400        // 방당 수집 상한

func attr(_ e: AXUIElement, _ k: String) -> CFTypeRef? { var v: CFTypeRef?; AXUIElementCopyAttributeValue(e, k as CFString, &v); return v }
func kids(_ e: AXUIElement) -> [AXUIElement] { (attr(e, kAXChildrenAttribute) as? [AXUIElement]) ?? [] }
func role(_ e: AXUIElement) -> String { (attr(e, kAXRoleAttribute) as? String) ?? "" }
func text(_ e: AXUIElement) -> String { (attr(e, kAXValueAttribute) as? String) ?? (attr(e, kAXTitleAttribute) as? String) ?? "" }
func windows(_ app: AXUIElement) -> [AXUIElement] { (attr(app, kAXWindowsAttribute) as? [AXUIElement]) ?? [] }
func title(_ w: AXUIElement) -> String { (attr(w, kAXTitleAttribute) as? String) ?? "" }
func out(_ obj: [String: Any]) {
    let d = try! JSONSerialization.data(withJSONObject: obj)
    FileHandle.standardOutput.write(d)
}

let timeRe = try! NSRegularExpression(pattern: "^(오전|오후) ?\\d{1,2}:\\d{2}$")
func isTime(_ s: String) -> Bool { timeRe.firstMatch(in: s, range: NSRange(s.startIndex..., in: s)) != nil }
let dateRe = try! NSRegularExpression(pattern: "^\\d{4}년 \\d{1,2}월 \\d{1,2}일")
func isDate(_ s: String) -> Bool { dateRe.firstMatch(in: s, range: NSRange(s.startIndex..., in: s)) != nil }

guard AXIsProcessTrusted() else {
    out(["rooms": [], "error": "손쉬운 사용 권한이 필요합니다"]); exit(2)
}
guard let running = NSRunningApplication.runningApplications(withBundleIdentifier: BUNDLE).first else {
    out(["rooms": [], "error": "카카오톡이 실행 중이 아닙니다"]); exit(0)
}
let pid = running.processIdentifier
let app = AXUIElementCreateApplication(pid)

// 메인(채팅 목록) 창이 없으면 띄운다
var openedMain = false
if !windows(app).contains(where: { title($0) == "카카오톡" }) {
    // 이미 실행 중인 카톡은 'open -b' 로 다시 열어야 목록 창이 뜬다
    let p = Process(); p.executableURL = URL(fileURLWithPath: "/usr/bin/open"); p.arguments = ["-b", BUNDLE]
    try? p.run(); p.waitUntilExit()
    openedMain = true
    for _ in 0..<40 { usleep(200_000); if windows(app).contains(where: { title($0) == "카카오톡" }) { break } }
}
guard let main = windows(app).first(where: { title($0) == "카카오톡" }) else {
    out(["rooms": [], "error": "카카오톡 창을 찾지 못했습니다"]); exit(0)
}

// 채팅 목록에서 오늘(시간 표시가 '오전/오후 h:mm') 방만
struct Room { let row: AXUIElement; let name: String; let unread: Int }
var rooms: [Room] = []
func collectRows(_ e: AXUIElement) {
    for k in kids(e) {
        if role(k) == "AXRow" {
            var texts: [String] = []
            func scan(_ x: AXUIElement) { for c in kids(x) { if role(c) == "AXStaticText" { texts.append(text(c)) }; scan(c) } }
            scan(k)
            if let name = texts.first, texts.dropFirst().contains(where: isTime) {
                let unread = texts.dropFirst().compactMap { Int($0) }.first ?? 0
                rooms.append(Room(row: k, name: name, unread: unread))
            }
        } else { collectRows(k) }
    }
}
for _ in 0..<40 {            // 창을 막 띄웠으면 목록이 그려질 때까지 기다린다(최대 8초)
    rooms = []; collectRows(main)
    if !rooms.isEmpty { break }
    usleep(200_000)
}
if ProcessInfo.processInfo.environment["KAKAO_SKIP_UNREAD"] == "1" { rooms = rooms.filter { $0.unread == 0 } }   // 시험용
rooms = Array(rooms.prefix(Int(ProcessInfo.processInfo.environment["KAKAO_MAX_ROOMS"] ?? "") ?? MAX_ROOMS))

func minutes(_ s: String) -> Int? {
    let p = s.replacingOccurrences(of: " ", with: "")
    guard p.count >= 6 else { return nil }
    let pm = p.hasPrefix("오후"), body = p.dropFirst(2).split(separator: ":")
    guard body.count == 2, var h = Int(body[0]), let m = Int(body[1]) else { return nil }
    if h == 12 { h = 0 }
    return (pm ? h + 12 : h) * 60 + m
}

func collectItems(_ w: AXUIElement) -> [(String, String)] {
    var items: [(String, String)] = []
    func walk(_ e: AXUIElement) {
        for k in kids(e) {
            let r = role(k), t = text(k)
            if (r == "AXStaticText" || r == "AXTextArea") && !t.isEmpty { items.append((r, t)) }
            walk(k)
        }
    }
    walk(w)
    return items
}

// 수집 범위 안에 '어제 경계'가 들어왔는가: 오늘이 아닌 날짜 구분선, 또는 문서 순서(과거→최신)에서 시각이 뚝 떨어지는 지점
func boundaryLoaded(_ items: [(String, String)], _ todayLabel: String) -> Bool {
    var times: [Int] = []
    for (r, t) in items where r == "AXStaticText" {
        if isDate(t) && !t.hasPrefix(todayLabel) { return true }
        if isTime(t), let v = minutes(t) { times.append(v) }
    }
    if times.count > 1 {
        for i in 1..<times.count where times[i] < times[i - 1] { return true }
    }
    return false
}

func parseMsgs(_ items: [(String, String)], _ name: String, _ todayLabel: String) -> [[String: String]] {
    var msgs: [[String: String]] = []
    var curTime = "", curFrom = "나", seenToday = false, anyDate = false
    for (r, t) in items {
        if r == "AXStaticText" {
            if isDate(t) { anyDate = true; seenToday = t.hasPrefix(todayLabel); continue }
            if isTime(t) { curTime = t; curFrom = "나"; continue }
            if t == name && msgs.isEmpty && curTime.isEmpty { continue }   // 창 머리의 방 이름
            curFrom = t
        } else {
            if anyDate && !seenToday { continue }                        // 날짜 구분선이 보이면 오늘 것만
            msgs.append(["time": curTime, "from": curFrom, "text": t])
        }
    }
    return msgs
}

// 위로 한 페이지: 접근성 스크롤바 값을 직접 내리고(1순위), 안 되면 PageUp 키(폴백)
func scrollUp(_ w: AXUIElement, _ pid: pid_t, _ src: CGEventSource?) -> String {
    func findScrollBar(_ e: AXUIElement, _ depth: Int) -> AXUIElement? {
        if depth > 12 { return nil }
        if role(e) == "AXScrollArea", let sb = attr(e, "AXVerticalScrollBar"),
           CFGetTypeID(sb) == AXUIElementGetTypeID() {
            return (sb as! AXUIElement)
        }
        for k in kids(e) { if let f = findScrollBar(k, depth + 1) { return f } }
        return nil
    }
    if let sb = findScrollBar(w, 0), let cur = attr(sb, kAXValueAttribute) as? Double {
        let next = max(0.0, cur - 0.5)
        if next < cur {
            var v = next
            if let num = CFNumberCreate(nil, .doubleType, &v),
               AXUIElementSetAttributeValue(sb, kAXValueAttribute as CFString, num) == .success {
                return "bar \(String(format: "%.2f", cur))→\(String(format: "%.2f", next))"
            }
        } else { return "bar top" }
    }
    if let src = src {
        for down in [true, false] { CGEvent(keyboardEventSource: src, virtualKey: 116, keyDown: down)!.postToPid(pid) }
    }
    return "pageup"
}

func readRoom(_ w: AXUIElement, _ name: String, _ pid: pid_t, _ src: CGEventSource?) -> [[String: String]] {
    let f = DateFormatter(); f.locale = Locale(identifier: "ko_KR"); f.dateFormat = "yyyy년 M월 d일"
    let todayLabel = f.string(from: Date())
    let debug = ProcessInfo.processInfo.environment["KAKAO_DEBUG"] == "1"

    // 아침 대화까지 확보: 어제 경계가 로드될 때까지 PageUp으로 과거를 불러오며 수집
    var acc: [[String: String]] = []
    var lastSig = ""
    var stuck = 0
    for pass in 0...MAX_SCROLLS {
        let items = collectItems(w)
        let msgs = parseMsgs(items, name, todayLabel)
        if debug {
            FileHandle.standardError.write("[\(name)] pass \(pass): items \(items.count), msgs \(msgs.count)\n".data(using: .utf8)!)
        }
        // 패스 병합: 새 패스(msgs)가 누적(acc)의 앞부분을 포함하면 교체, 아니면 겹침 지점 앞부분만 이어 붙임
        if acc.isEmpty {
            acc = msgs
        } else if !msgs.isEmpty {
            let probe = Array(acc.prefix(3))
            var joined = false
            if msgs.count >= probe.count {
                for s in stride(from: msgs.count - probe.count, through: 0, by: -1) {
                    if Array(msgs[s..<s + probe.count]) == probe {
                        acc = Array(msgs[0..<s]) + acc
                        joined = true
                        break
                    }
                }
            }
            if !joined { acc = msgs + acc.filter { m in !msgs.contains(m) } }
        }
        if boundaryLoaded(items, todayLabel) {
            if debug { FileHandle.standardError.write("[\(name)] pass \(pass): 어제 경계 확인 — 중단\n".data(using: .utf8)!) }
            break
        }
        if acc.count >= MAX_MSGS { break }
        let sig = "\(items.count)|\(items.first?.1 ?? "")"
        if sig == lastSig { stuck += 1; if stuck >= 2 { break } } else { stuck = 0 }   // 맨 위 도달
        lastSig = sig
        if pass == MAX_SCROLLS { break }
        let how = scrollUp(w, pid, src)
        if debug { FileHandle.standardError.write("[\(name)] scroll: \(how)\n".data(using: .utf8)!) }
        usleep(350_000)
    }

    // 날짜 구분선은 접근성으로 안 보인다 → 끝(가장 최근)부터 거꾸로 가며 시각이 다시 커지는 곳에서 끊는다(전날)
    var today: [[String: String]] = []
    var last = Int.max
    for m in acc.reversed() {
        if let v = minutes(m["time"] ?? "") {
            if v > last { break }
            last = v
        }
        today.append(m)
        if today.count >= MAX_MSGS { break }
    }
    return today.reversed()
}

var result: [[String: Any]] = []
let src = CGEventSource(stateID: .hidSystemState)
for room in rooms {
    let already = windows(app).first(where: { title($0) == room.name })
    var w = already
    if w == nil {
        AXUIElementSetAttributeValue(room.row, kAXSelectedAttribute as CFString, kCFBooleanTrue)
        usleep(200_000)
        for down in [true, false] { CGEvent(keyboardEventSource: src, virtualKey: 36, keyDown: down)!.postToPid(pid) }
        for _ in 0..<20 { usleep(150_000); if let x = windows(app).first(where: { title($0) == room.name }) { w = x; break } }
    }
    guard let win = w else { continue }
    usleep(400_000)
    let msgs = readRoom(win, room.name, pid, src)
    if !msgs.isEmpty { result.append(["room": room.name, "unread": room.unread, "messages": msgs]) }
    if already == nil, let b = attr(win, kAXCloseButtonAttribute) {
        AXUIElementPerformAction(b as! AXUIElement, kAXPressAction as CFString)
    }
}
if openedMain, let b = attr(main, kAXCloseButtonAttribute) {
    AXUIElementPerformAction(b as! AXUIElement, kAXPressAction as CFString)
}
out(["rooms": result])
