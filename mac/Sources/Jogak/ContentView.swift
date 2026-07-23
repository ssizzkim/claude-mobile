import SwiftUI

func chipColor(_ code: String) -> Color {
    switch code {
    case "c2": return .green
    case "c3": return .orange
    case "c4": return .purple
    default: return .blue
    }
}

struct ContentView: View {
    @EnvironmentObject var store: Store
    @State private var filter: SidebarFilter? = SidebarFilter.all
    @State private var search = ""
    @State private var composePresented = false
    @State private var editingCard: JCard? = nil

    @State private var addFolderPresented = false
    @State private var newFolderName = ""
    @State private var renameTargetID: String? = nil
    @State private var renameText = ""

    private var currentFilter: SidebarFilter { filter ?? .all }

    var body: some View {
        NavigationSplitView {
            sidebar
        } detail: {
            cardList
        }
        .sheet(isPresented: $composePresented) {
            ComposeView(card: editingCard)
                .environmentObject(store)
        }
        .alert("새 서랍", isPresented: $addFolderPresented) {
            TextField("서랍 이름", text: $newFolderName)
            Button("만들기") {
                store.addFolder(name: newFolderName)
                newFolderName = ""
            }
            Button("취소", role: .cancel) { newFolderName = "" }
        }
        .alert("서랍 이름 변경", isPresented: Binding(
            get: { renameTargetID != nil },
            set: { if !$0 { renameTargetID = nil } }
        )) {
            TextField("서랍 이름", text: $renameText)
            Button("변경") {
                if let id = renameTargetID, let f = store.folder(id) {
                    store.renameFolder(f, to: renameText)
                }
                renameTargetID = nil
            }
            Button("취소", role: .cancel) { renameTargetID = nil }
        }
    }

    // MARK: - sidebar

    private var sidebar: some View {
        List(selection: $filter) {
            HStack {
                Text("▤ 전체 조각")
                Spacer()
                Text("\(store.count(for: .all))").foregroundStyle(.secondary).monospacedDigit()
            }
            .tag(SidebarFilter.all)

            Section("서랍") {
                ForEach(store.folders) { f in
                    HStack {
                        Text("\(f.icon) \(f.name)")
                        Spacer()
                        Text("\(store.count(for: .folder(f.id)))")
                            .foregroundStyle(.secondary).monospacedDigit()
                    }
                    .tag(SidebarFilter.folder(f.id))
                    .contextMenu {
                        Button("이름 변경") {
                            renameText = f.name
                            renameTargetID = f.id
                        }
                        Button("삭제", role: .destructive) {
                            store.deleteFolder(f)
                            if currentFilter == .folder(f.id) { filter = .all }
                        }
                    }
                }

                HStack {
                    Text("⋯ 미분류함").foregroundStyle(.secondary)
                    Spacer()
                    Text("\(store.count(for: .unfiled))")
                        .foregroundStyle(.secondary).monospacedDigit()
                }
                .tag(SidebarFilter.unfiled)
            }

            Button {
                addFolderPresented = true
            } label: {
                Label("새 서랍", systemImage: "plus")
            }
            .buttonStyle(.plain)
            .foregroundStyle(.secondary)
        }
        .navigationSplitViewColumnWidth(min: 180, ideal: 220)
    }

    // MARK: - card list

    private var titleText: String {
        switch currentFilter {
        case .all: return "조각"
        case .unfiled: return "미분류함"
        case .folder(let id): return store.folder(id)?.name ?? "조각"
        }
    }

    private var cardList: some View {
        let cards = store.visibleCards(filter: currentFilter, search: search)
        return Group {
            if cards.isEmpty {
                VStack(spacing: 10) {
                    Text("✂").font(.system(size: 40))
                    Text(search.isEmpty ? "아직 조각이 없어요.\n⌘N으로 첫 조각을 남겨보세요." : "검색 결과가 없어요.")
                        .multilineTextAlignment(.center)
                        .foregroundStyle(.secondary)
                }
                .frame(maxWidth: .infinity, maxHeight: .infinity)
            } else {
                List(cards) { card in
                    CardRow(card: card)
                        .contentShape(Rectangle())
                        .onTapGesture {
                            editingCard = card
                            composePresented = true
                        }
                        .contextMenu {
                            Button(card.pinned ? "고정 해제" : "고정") { store.togglePin(card) }
                            Button("수정") {
                                editingCard = card
                                composePresented = true
                            }
                            Button("삭제", role: .destructive) { store.deleteCard(card) }
                        }
                }
                .listStyle(.inset)
            }
        }
        .navigationTitle(titleText)
        .searchable(text: $search, placement: .toolbar, prompt: "조각 검색")
        .toolbar {
            ToolbarItem(placement: .primaryAction) {
                Button {
                    editingCard = nil
                    composePresented = true
                } label: {
                    Label("새 조각", systemImage: "plus")
                }
                .keyboardShortcut("n", modifiers: .command)
            }
        }
    }
}

struct CardRow: View {
    @EnvironmentObject var store: Store
    let card: JCard

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack(alignment: .top) {
                Text(card.text)
                    .font(.system(size: 14))
                    .lineLimit(6)
                if card.pinned {
                    Spacer()
                    Text("📌").font(.system(size: 11))
                }
            }
            HStack(spacing: 6) {
                ForEach(card.folders, id: \.self) { fid in
                    if let f = store.folder(fid) {
                        Text(f.name)
                            .font(.system(size: 10.5, weight: .semibold))
                            .padding(.horizontal, 8)
                            .padding(.vertical, 2)
                            .background(Capsule().fill(chipColor(f.color).opacity(0.15)))
                            .foregroundStyle(chipColor(f.color))
                    }
                }
                Spacer()
                Text(ISO.display(card.created_at))
                    .font(.system(size: 11))
                    .foregroundStyle(.secondary)
                    .monospacedDigit()
            }
        }
        .padding(.vertical, 6)
    }
}
