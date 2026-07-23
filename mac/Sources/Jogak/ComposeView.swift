import SwiftUI

struct ComposeView: View {
    @EnvironmentObject var store: Store
    @Environment(\.dismiss) private var dismiss

    let card: JCard?
    @State private var text: String
    @State private var selected: Set<String>

    init(card: JCard?) {
        self.card = card
        _text = State(initialValue: card?.text ?? "")
        _selected = State(initialValue: Set(card?.folders ?? []))
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            Text(card == nil ? "새 조각" : "조각 수정")
                .font(.title3.bold())

            TextEditor(text: $text)
                .font(.system(size: 15))
                .scrollContentBackground(.hidden)
                .padding(10)
                .frame(minHeight: 150)
                .background(
                    RoundedRectangle(cornerRadius: 10)
                        .fill(Color(nsColor: .textBackgroundColor))
                )
                .overlay(
                    RoundedRectangle(cornerRadius: 10)
                        .strokeBorder(Color.secondary.opacity(0.25))
                )

            Text("서랍 선택 — 여러 개 가능")
                .font(.caption)
                .foregroundStyle(.secondary)

            LazyVGrid(columns: [GridItem(.adaptive(minimum: 110), spacing: 6)], alignment: .leading, spacing: 6) {
                ForEach(store.folders) { f in
                    let isOn = selected.contains(f.id)
                    Button {
                        if isOn { selected.remove(f.id) } else { selected.insert(f.id) }
                    } label: {
                        Text((isOn ? "✓ " : "") + f.name)
                            .font(.system(size: 12, weight: .semibold))
                            .padding(.horizontal, 10)
                            .padding(.vertical, 4)
                            .frame(maxWidth: .infinity)
                            .background(
                                Capsule().fill(chipColor(f.color).opacity(isOn ? 0.35 : 0.12))
                            )
                            .foregroundStyle(chipColor(f.color))
                    }
                    .buttonStyle(.plain)
                }
            }

            HStack {
                if card != nil {
                    Button("삭제", role: .destructive) {
                        if let card { store.deleteCard(card) }
                        dismiss()
                    }
                }
                Spacer()
                Button("취소") { dismiss() }
                    .keyboardShortcut(.escape, modifiers: [])
                Button(card == nil ? "조각 저장" : "수정 완료") {
                    let trimmed = text.trimmingCharacters(in: .whitespacesAndNewlines)
                    guard !trimmed.isEmpty else { return }
                    store.upsertCard(id: card?.id, text: trimmed, folderIDs: Array(selected))
                    dismiss()
                }
                .keyboardShortcut(.return, modifiers: .command)
                .buttonStyle(.borderedProminent)
                .disabled(text.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
            }
        }
        .padding(20)
        .frame(minWidth: 480, minHeight: 400)
    }
}
