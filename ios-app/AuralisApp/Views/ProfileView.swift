import SwiftUI
import PhotosUI

struct ProfileView: View {
    @EnvironmentObject private var session: SessionStore
    @EnvironmentObject private var settings: SettingsStore
    @EnvironmentObject private var documents: DocumentsStore
    @EnvironmentObject private var toasts: ToastStore
    @EnvironmentObject private var avatar: AvatarStore

    @State private var showPasswordSheet = false
    @State private var confirmDelete = false
    @State private var safariItem: SafariItem?
    @State private var photoItem: PhotosPickerItem?
    @Environment(\.openURL) private var openURL

    var body: some View {
        ScrollView {
            VStack(spacing: 24) {
                clientCard

                // Preferences
                groupCard {
                    languageRow
                    if SettingsStore.biometricsAvailable {
                        rowDivider
                        faceIDRow
                    }
                }

                // Account & links
                groupCard {
                    buttonRow(icon: "key", title: L10n["profile.password"]) {
                        showPasswordSheet = true
                    }
                    rowDivider
                    documentsRow
                    rowDivider
                    buttonRow(icon: "globe", title: L10n["profile.website"]) {
                        if let url = URL(string: "https://www.auralisnatura.com") {
                            safariItem = SafariItem(url: url)
                        }
                    }
                    rowDivider
                    buttonRow(icon: "envelope", title: L10n["profile.support"]) {
                        if let url = URL(string: "mailto:team@auralisnatura.com") {
                            openURL(url)
                        }
                    }
                    rowDivider
                    buttonRow(icon: "hand.raised", title: L10n["profile.privacy"]) {
                        if let url = URL(string: "https://www.auralisnatura.com/impressum.html") {
                            safariItem = SafariItem(url: url)
                        }
                    }
                }

                // Sensitive actions
                groupCard {
                    buttonRow(icon: "trash", title: L10n["profile.delete"], tint: AN.warn) {
                        confirmDelete = true
                    }
                    rowDivider
                    buttonRow(icon: "rectangle.portrait.and.arrow.right",
                              title: L10n["profile.logout"], tint: AN.warn) {
                        session.logout()
                    }
                }

                Text(L10n.f("profile.version", appVersion))
                    .font(ANFont.text(11))
                    .monospacedDigit()
                    .foregroundStyle(AN.inkFaint)
                    .frame(maxWidth: .infinity)
                    .padding(.top, 4)
            }
            .padding(20)
        }
        .background(AN.paper.ignoresSafeArea())
        .task { if let id = session.me?.clientId { avatar.load(for: id) } }
        .onChange(of: session.me?.clientId) { _, id in if let id { avatar.load(for: id) } }
        .onChange(of: photoItem) { _, item in loadPickedPhoto(item) }
        .sheet(isPresented: $showPasswordSheet) { ChangePasswordSheet() }
        .sheet(item: $safariItem) { SafariView(url: $0.url) }
        .alert(L10n["profile.delete.confirm.title"], isPresented: $confirmDelete) {
            Button(L10n["common.cancel"], role: .cancel) {}
            Button(L10n["profile.delete"], role: .destructive) { requestDeletion() }
        } message: {
            Text(L10n["profile.delete.confirm.msg"])
        }
    }

    private var appVersion: String {
        (Bundle.main.infoDictionary?["CFBundleShortVersionString"] as? String) ?? "1.0"
    }

    // MARK: Client card

    private var clientCard: some View {
        HStack(spacing: 14) {
            avatarPicker
            VStack(alignment: .leading, spacing: 3) {
                Text(session.me?.name ?? "—")
                    .font(ANFont.text(17, weight: .semibold))
                    .foregroundStyle(AN.ink)
                Text("\(L10n["profile.clientId"]) · \(session.me?.clientId ?? "—")")
                    .font(ANFont.text(13))
                    .monospacedDigit()
                    .foregroundStyle(AN.inkSoft)
            }
            Spacer()
            SparkDots()
        }
        .padding(16)
        .anCard()
    }

    /// Tappable avatar: shows the client's photo if set, otherwise their
    /// initials, with a small camera badge inviting them to add/replace it.
    private var avatarPicker: some View {
        PhotosPicker(selection: $photoItem, matching: .images, photoLibrary: .shared()) {
            ZStack {
                if let img = avatar.image {
                    Image(uiImage: img)
                        .resizable()
                        .scaledToFill()
                } else {
                    Circle().fill(AN.sageSoft)
                    Text(initials)
                        .font(ANFont.display(20, weight: .semibold))
                        .foregroundStyle(AN.forest)
                }
            }
            .frame(width: 56, height: 56)
            .clipShape(Circle())
            .overlay(Circle().strokeBorder(AN.hairline, lineWidth: 1))
            .overlay(alignment: .bottomTrailing) {
                Image(systemName: "camera.fill")
                    .font(.system(size: 9, weight: .semibold))
                    .foregroundStyle(AN.cream)
                    .frame(width: 20, height: 20)
                    .background(AN.clay)
                    .clipShape(Circle())
                    .overlay(Circle().strokeBorder(AN.paper, lineWidth: 2))
            }
            .accessibilityLabel(L10n["profile.photo.change"])
        }
        .buttonStyle(.plain)
        .contextMenu {
            if avatar.image != nil {
                Button(role: .destructive) {
                    if let id = session.me?.clientId { avatar.remove(for: id) }
                    Haptics.tap()
                } label: {
                    Label(L10n["profile.photo.remove"], systemImage: "trash")
                }
            }
        }
    }

    private func loadPickedPhoto(_ item: PhotosPickerItem?) {
        guard let item, let id = session.me?.clientId else { return }
        Task {
            if let data = try? await item.loadTransferable(type: Data.self) {
                avatar.save(data, for: id)
                Haptics.success()
                toasts.show(L10n["profile.photo.saved"])
            } else {
                toasts.show(L10n["error.generic"], kind: .error)
            }
            photoItem = nil
        }
    }

    private var initials: String {
        let parts = (session.me?.name ?? "").split(separator: " ").prefix(2)
        let letters = parts.compactMap { $0.first.map(String.init) }
        return letters.isEmpty ? "·" : letters.joined()
    }

    // MARK: Row building blocks

    private func groupCard(@ViewBuilder content: () -> some View) -> some View {
        VStack(spacing: 0) { content() }.anCard()
    }

    private var rowDivider: some View {
        Rectangle().fill(AN.hairline).frame(height: 1).padding(.leading, 52)
    }

    private func rowLabel(icon: String, title: String, tint: Color = AN.ink) -> some View {
        HStack(spacing: 12) {
            Image(systemName: icon)
                .font(.system(size: 17, weight: .light))
                .foregroundStyle(tint == AN.ink ? AN.forest : tint)
                .frame(width: 26)
            Text(title)
                .font(ANFont.text(15, weight: .medium))
                .foregroundStyle(tint)
        }
    }

    private func buttonRow(icon: String, title: String, tint: Color = AN.ink,
                           action: @escaping () -> Void) -> some View {
        Button {
            Haptics.tap()
            action()
        } label: {
            HStack {
                rowLabel(icon: icon, title: title, tint: tint)
                Spacer()
                Image(systemName: "chevron.right")
                    .font(.system(size: 12, weight: .semibold))
                    .foregroundStyle(AN.inkFaint)
            }
            .padding(14)
            .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
    }

    private var languageRow: some View {
        Menu {
            ForEach(["de", "en", "es"], id: \.self) { lang in
                Button {
                    settings.lang = lang
                } label: {
                    if settings.lang == lang {
                        Label(L10n["lang.\(lang)"], systemImage: "checkmark")
                    } else {
                        Text(L10n["lang.\(lang)"])
                    }
                }
            }
        } label: {
            HStack {
                rowLabel(icon: "globe", title: L10n["profile.language"])
                Spacer()
                Text(L10n["lang.\(settings.lang)"])
                    .font(ANFont.text(14))
                    .foregroundStyle(AN.inkSoft)
                Image(systemName: "chevron.up.chevron.down")
                    .font(.system(size: 11, weight: .semibold))
                    .foregroundStyle(AN.inkFaint)
            }
            .padding(14)
            .contentShape(Rectangle())
        }
    }

    private var faceIDRow: some View {
        Toggle(isOn: $settings.faceIDEnabled) {
            rowLabel(icon: "faceid", title: L10n["profile.faceid"])
        }
        .tint(AN.forest)
        .padding(14)
    }

    private var documentsRow: some View {
        NavigationLink {
            JourneyView()
        } label: {
            HStack {
                rowLabel(icon: "doc.text", title: L10n["profile.docs"])
                Spacer()
                if !documents.docs.isEmpty {
                    Text("\(documents.docs.count)")
                        .font(ANFont.text(12, weight: .semibold))
                        .monospacedDigit()
                        .foregroundStyle(AN.cream)
                        .padding(.horizontal, 8)
                        .padding(.vertical, 3)
                        .background(AN.sage)
                }
                Image(systemName: "chevron.right")
                    .font(.system(size: 12, weight: .semibold))
                    .foregroundStyle(AN.inkFaint)
            }
            .padding(14)
            .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
    }

    // MARK: Deletion request

    private func requestDeletion() {
        Task { @MainActor in
            do {
                let _: OkResponse = try await APIClient.shared.post(
                    "/api/my/delete-request", body: EmptyBody())
                Haptics.success()
                toasts.show(L10n["profile.delete.sent"])
            } catch {
                toasts.show((error as? APIError)?.message ?? L10n["error.generic"], kind: .error)
            }
        }
    }
}

// MARK: - Change password sheet

struct ChangePasswordSheet: View {
    @Environment(\.dismiss) private var dismiss
    @EnvironmentObject private var toasts: ToastStore

    @State private var current = ""
    @State private var newPassword = ""
    @State private var repeatPassword = ""
    @State private var busy = false
    @State private var errorText: String?

    private var valid: Bool {
        !current.isEmpty && newPassword.count >= 8 && newPassword == repeatPassword
    }

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: 16) {
                    ANTextField(label: L10n["profile.password.current"],
                                text: $current, secure: true)
                    ANTextField(label: L10n["profile.password.new"],
                                text: $newPassword, secure: true)
                    ANTextField(label: L10n["profile.password.repeat"],
                                text: $repeatPassword, secure: true)
                    Text(L10n["profile.password.rule"])
                        .font(ANFont.text(12))
                        .foregroundStyle(AN.inkFaint)
                        .frame(maxWidth: .infinity, alignment: .leading)
                    if let errorText {
                        Text(errorText)
                            .font(ANFont.text(13, weight: .medium))
                            .foregroundStyle(AN.warn)
                            .frame(maxWidth: .infinity, alignment: .leading)
                    }
                    Button {
                        save()
                    } label: {
                        if busy {
                            ProgressView().tint(AN.cream)
                        } else {
                            Text(L10n["common.send"])
                        }
                    }
                    .buttonStyle(.anPrimary)
                    .disabled(!valid || busy)
                    .padding(.top, 8)
                }
                .padding(20)
            }
            .scrollDismissesKeyboard(.interactively)
            .background(AN.paper.ignoresSafeArea())
            .navigationTitle(L10n["profile.password"])
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarLeading) {
                    Button(L10n["common.cancel"]) { dismiss() }
                        .font(ANFont.text(15))
                        .foregroundStyle(AN.inkSoft)
                        .disabled(busy)
                }
            }
        }
        .presentationDetents([.medium, .large])
    }

    private func save() {
        Haptics.tap()
        errorText = nil
        busy = true
        Task { @MainActor in
            do {
                let _: OkResponse = try await APIClient.shared.post(
                    "/api/my/change-password",
                    body: ChangePasswordBody(current: current, newPassword: newPassword))
                Haptics.success()
                toasts.show(L10n["profile.password.ok"])
                dismiss()
            } catch APIError.network {
                errorText = L10n["error.network"]
            } catch {
                errorText = L10n["profile.password.wrong"]
            }
            busy = false
        }
    }
}
