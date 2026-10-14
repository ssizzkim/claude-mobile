// 카카오톡 맥 앱에서 '오늘' 대화가 있는 방을 접근성으로 열어 읽고 닫는다 → JSON 출력.
// 저장 파일(암호화 DB)은 건드리지 않는다. 방을 열면 그 방의 안 읽은 메시지는 읽음 처리된다.
// 종료 코드 2 = 손쉬운 사용(접근성) 권한 없음.
import Cocoa
import ApplicationServices

let BUNDLE = "com.kakao.KakaoTalkMac"
let MAX_ROOMS = 30

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

func readRoom(_ w: AXUIElement, _ name: String) -> [[String: String]] {
    var msgs: [[String: String]] = []
    var curTime = "", curFrom = "나", seenToday = false, anyDate = false
    var items: [(String, String)] = []
    func walk(_ e: AXUIElement) {
        for k in kids(e) {
            let r = role(k), t = text(k)
            if (r == "AXStaticText" || r == "AXTextArea") && !t.isEmpty { items.append((r, t)) }
            walk(k)
        }
    }
    walk(w)
    if ProcessInfo.processInfo.environment["KAKAO_DEBUG"] == "1" {
        for (r, t) in items where r == "AXStaticText" && !isTime(t) { FileHandle.standardError.write("[\(name)] \(t)\n".data(using: .utf8)!) }
    }
    let f = DateFormatter(); f.locale = Locale(identifier: "ko_KR"); f.dateFormat = "yyyy년 M월 d일"
    let todayLabel = f.string(from: Date())
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
    // 날짜 구분선은 접근성으로 안 보인다 → 끝(가장 최근)부터 거꾸로 가며 시각이 다시 커지는 곳에서 끊는다(전날)
    func minutes(_ s: String) -> Int? {
        let p = s.replacingOccurrences(of: " ", with: "")
        guard p.count >= 6 else { return nil }
        let pm = p.hasPrefix("오후"), body = p.dropFirst(2).split(separator: ":")
        guard body.count == 2, var h = Int(body[0]), let m = Int(body[1]) else { return nil }
        if h == 12 { h = 0 }
        return (pm ? h + 12 : h) * 60 + m
    }
    var today: [[String: String]] = []
    var last = Int.max
    for m in msgs.reversed() {
        if let v = minutes(m["time"] ?? "") {
            if v > last { break }
            last = v
        }
        today.append(m)
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
    let msgs = readRoom(win, room.name)
    if !msgs.isEmpty { result.append(["room": room.name, "unread": room.unread, "messages": msgs]) }
    if already == nil, let b = attr(win, kAXCloseButtonAttribute) {
        AXUIElementPerformAction(b as! AXUIElement, kAXPressAction as CFString)
    }
}
if openedMain, let b = attr(main, kAXCloseButtonAttribute) {
    AXUIElementPerformAction(b as! AXUIElement, kAXPressAction as CFString)
}
out(["rooms": result])
