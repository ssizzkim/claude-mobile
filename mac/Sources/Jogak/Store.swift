import Foundation
import Combine

enum SidebarFilter: Hashable {
    case all
    case unfiled
    case folder(String)
}

final class Store: ObservableObject {
    @Published var cards: [JCard] = []
    @Published var folders: [JFolder] = []

    private var fileURL: URL {
        let base = FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask)[0]
        let dir = base.appendingPathComponent("Jogak", isDirectory: true)
        try? FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        return dir.appendingPathComponent("jogak.json")
    }

    init() {
        load()
    }

    // MARK: - persistence

    func load() {
        if let data = try? Data(contentsOf: fileURL),
           let decoded = try? JSONDecoder().decode(StoreData.self, from: data) {
            folders = decoded.folders
            cards = decoded.cards
            return
        }
        seed()
        save()
    }

    func save() {
        let payload = StoreData(version: 1, folders: folders, cards: cards)
        let encoder = JSONEncoder()
        encoder.outputFormatting = [.prettyPrinted, .sortedKeys]
        if let data = try? encoder.encode(payload) {
            try? data.write(to: fileURL, options: .atomic)
        }
    }

    private func seed() {
        let now = ISO.now()
        folders = [
            JFolder(id: "f_idea", name: "아이디어", icon: "💡", color: "c1", created_at: now),
            JFolder(id: "f_read", name: "독서 메모", icon: "📖", color: "c2", created_at: now),
            JFolder(id: "f_quote", name: "인용", icon: "❝", color: "c3", created_at: now),
            JFolder(id: "f_diary", name: "일기 조각", icon: "🌙", color: "c4", created_at: now),
        ]
        cards = [
            JCard(id: newID("card"),
                  text: "조각 맥 앱에 오신 걸 환영해요.\n\n⌘N으로 새 조각을 쓰고, 왼쪽 서랍으로 정리해 보세요. 이 카드는 지워도 됩니다.",
                  folders: ["f_idea"], created_at: now, updated_at: now, pinned: true),
        ]
    }

    // MARK: - queries

    func visibleCards(filter: SidebarFilter, search: String) -> [JCard] {
        let q = search.trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
        return cards
            .filter { card in
                if card.archived { return false }
                switch filter {
                case .all: break
                case .unfiled:
                    if !card.folders.isEmpty { return false }
                case .folder(let id):
                    if !card.folders.contains(id) { return false }
                }
                if !q.isEmpty && !card.text.lowercased().contains(q) { return false }
                return true
            }
            .sorted { a, b in
                if a.pinned != b.pinned { return a.pinned }
                return a.created_at > b.created_at
            }
    }

    func count(for filter: SidebarFilter) -> Int {
        visibleCards(filter: filter, search: "").count
    }

    func folder(_ id: String) -> JFolder? {
        folders.first { $0.id == id }
    }

    // MARK: - card mutations

    func upsertCard(id: String?, text: String, folderIDs: [String]) {
        let now = ISO.now()
        if let id, let idx = cards.firstIndex(where: { $0.id == id }) {
            cards[idx].text = text
            cards[idx].folders = folderIDs
            cards[idx].updated_at = now
        } else {
            cards.append(JCard(id: newID("card"), text: text, folders: folderIDs,
                               created_at: now, updated_at: now))
        }
        save()
    }

    func togglePin(_ card: JCard) {
        guard let idx = cards.firstIndex(where: { $0.id == card.id }) else { return }
        cards[idx].pinned.toggle()
        save()
    }

    func deleteCard(_ card: JCard) {
        cards.removeAll { $0.id == card.id }
        save()
    }

    // MARK: - folder mutations

    private static let chipColors = ["c1", "c2", "c3", "c4"]

    func addFolder(name: String) {
        let trimmed = name.trimmingCharacters(in: .whitespaces)
        guard !trimmed.isEmpty else { return }
        folders.append(JFolder(id: newID("f"), name: trimmed, icon: "🗂",
                               color: Self.chipColors[folders.count % Self.chipColors.count],
                               created_at: ISO.now()))
        save()
    }

    func renameFolder(_ folder: JFolder, to name: String) {
        let trimmed = name.trimmingCharacters(in: .whitespaces)
        guard !trimmed.isEmpty, let idx = folders.firstIndex(where: { $0.id == folder.id }) else { return }
        folders[idx].name = trimmed
        save()
    }

    func deleteFolder(_ folder: JFolder) {
        folders.removeAll { $0.id == folder.id }
        for idx in cards.indices {
            cards[idx].folders.removeAll { $0 == folder.id }
        }
        save()
    }

    // MARK: - import (웹 앱 JSON 백업 병합)

    func importBackup(from url: URL) -> String {
        guard let data = try? Data(contentsOf: url),
              let incoming = try? JSONDecoder().decode(StoreData.self, from: data) else {
            return "조각 백업 파일이 아니에요"
        }
        var addedF = 0, addedC = 0, updatedC = 0
        for f in incoming.folders where folder(f.id) == nil {
            folders.append(f)
            addedF += 1
        }
        for c in incoming.cards {
            if let idx = cards.firstIndex(where: { $0.id == c.id }) {
                if c.updated_at > cards[idx].updated_at {
                    cards[idx] = c
                    updatedC += 1
                }
            } else {
                cards.append(c)
                addedC += 1
            }
        }
        save()
        return "가져오기 완료 — 새 조각 \(addedC)개, 갱신 \(updatedC)개, 새 서랍 \(addedF)개"
    }
}
