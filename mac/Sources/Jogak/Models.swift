import Foundation

// 웹 앱(app/index.html)의 JSON 백업과 같은 필드명을 사용한다.
// 나중에 더보기 → JSON 백업 파일을 그대로 가져올 수 있게 하기 위함.

struct JFolder: Codable, Identifiable, Hashable {
    var id: String
    var name: String
    var icon: String
    var color: String
    var created_at: String
}

struct JCard: Codable, Identifiable, Hashable {
    var id: String
    var text: String
    var folders: [String]
    var created_at: String
    var updated_at: String
    var pinned: Bool
    var archived: Bool

    init(id: String, text: String, folders: [String],
         created_at: String, updated_at: String,
         pinned: Bool = false, archived: Bool = false) {
        self.id = id
        self.text = text
        self.folders = folders
        self.created_at = created_at
        self.updated_at = updated_at
        self.pinned = pinned
        self.archived = archived
    }

    // 웹 백업에는 attachments 등 추가 필드가 있어도 무시하고 읽는다.
    enum CodingKeys: String, CodingKey {
        case id, text, folders, created_at, updated_at, pinned, archived
    }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        id = try c.decode(String.self, forKey: .id)
        text = try c.decodeIfPresent(String.self, forKey: .text) ?? ""
        folders = try c.decodeIfPresent([String].self, forKey: .folders) ?? []
        created_at = try c.decodeIfPresent(String.self, forKey: .created_at) ?? ""
        updated_at = try c.decodeIfPresent(String.self, forKey: .updated_at) ?? created_at
        pinned = try c.decodeIfPresent(Bool.self, forKey: .pinned) ?? false
        archived = try c.decodeIfPresent(Bool.self, forKey: .archived) ?? false
    }
}

struct StoreData: Codable {
    var version: Int
    var folders: [JFolder]
    var cards: [JCard]
}

enum ISO {
    static func now() -> String {
        let f = ISO8601DateFormatter()
        f.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        return f.string(from: Date())
    }

    static func parse(_ s: String) -> Date? {
        let withFrac = ISO8601DateFormatter()
        withFrac.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        if let d = withFrac.date(from: s) { return d }
        let plain = ISO8601DateFormatter()
        plain.formatOptions = [.withInternetDateTime]
        return plain.date(from: s)
    }

    static func display(_ s: String) -> String {
        guard let d = parse(s) else { return s }
        let cal = Calendar.current
        let f = DateFormatter()
        f.locale = Locale(identifier: "ko_KR")
        if cal.isDateInToday(d) {
            f.dateFormat = "'오늘' HH:mm"
        } else if cal.isDateInYesterday(d) {
            f.dateFormat = "'어제' HH:mm"
        } else if cal.isDate(d, equalTo: Date(), toGranularity: .year) {
            f.dateFormat = "M.d"
        } else {
            f.dateFormat = "yyyy.M.d"
        }
        return f.string(from: d)
    }
}

func newID(_ prefix: String) -> String {
    let raw = UUID().uuidString.replacingOccurrences(of: "-", with: "").lowercased()
    return prefix + "_" + String(raw.prefix(10))
}
