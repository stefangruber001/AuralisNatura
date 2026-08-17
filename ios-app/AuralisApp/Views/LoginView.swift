import SwiftUI

struct LoginView: View {
    @EnvironmentObject private var session: SessionStore
    @EnvironmentObject private var settings: SettingsStore

    @State private var clientId = ""
    @State private var password = ""
    @State private var errorText: String?

    var body: some View {
        ScrollView {
            VStack(spacing: 0) {
                Spacer(minLength: 44)

                Image("Emblem")
                    .resizable()
                    .scaledToFit()
                    .frame(width: 84, height: 84)

                Text("Auralis Natura")
                    .font(ANFont.display(24, weight: .semibold))
                    .foregroundStyle(AN.forest)
                    .padding(.top, 14)

                Text(L10n["login.kicker"])
                    .font(ANFont.text(11, weight: .semibold))
                    .tracking(3)
                    .foregroundStyle(AN.clay)
                    .padding(.top, 6)

                Rectangle()
                    .fill(AN.gold)
                    .frame(width: 44, height: 1)
                    .padding(.top, 16)

                VStack(spacing: 14) {
                    ANTextField(label: L10n["login.clientId"],
                                text: $clientId,
                                uppercase: true,
                                contentType: .username)
                    ANTextField(label: L10n["login.password"],
                                text: $password,
                                secure: true,
                                contentType: .password)
                }
                .padding(.top, 30)

                if let errorText {
                    Text(errorText)
                        .font(ANFont.text(13, weight: .medium))
                        .foregroundStyle(AN.warn)
                        .multilineTextAlignment(.center)
                        .padding(.top, 12)
                }

                Button {
                    submit()
                } label: {
                    if session.busy {
                        ProgressView().tint(AN.cream)
                    } else {
                        Text(L10n["login.button"])
                    }
                }
                .buttonStyle(.anPrimary)
                .disabled(session.busy || trimmedId.isEmpty || password.isEmpty)
                .padding(.top, 20)

                if faceIDAvailable {
                    Button {
                        Haptics.tap()
                        errorText = nil
                        Task { await session.loginWithBiometrics() }
                    } label: {
                        Label(L10n["login.faceid"], systemImage: "faceid")
                    }
                    .buttonStyle(.anOutline)
                    .disabled(session.busy)
                    .padding(.top, 12)
                }

                guestDoor
                    .padding(.top, 26)

                languageRow
                    .padding(.top, 30)

                Text(L10n["login.footer"])
                    .font(ANFont.text(11))
                    .foregroundStyle(AN.sage)
                    .padding(.top, 22)
                    .padding(.bottom, 32)
            }
            .padding(.horizontal, 28)
            .frame(maxWidth: 480)
            .frame(maxWidth: .infinity)
        }
        .background(AN.paper.ignoresSafeArea())
        .scrollDismissesKeyboard(.interactively)
    }

    private var trimmedId: String {
        clientId.trimmingCharacters(in: .whitespacesAndNewlines)
    }

    private var faceIDAvailable: Bool {
        settings.faceIDEnabled
            && SettingsStore.biometricsAvailable
            && UserDefaults.standard.bool(forKey: "an_creds_saved")
    }

    private func submit() {
        Haptics.tap()
        errorText = nil
        let id = trimmedId
        let pw = password
        Task { @MainActor in
            do {
                try await session.login(id: id, password: pw)
                if let lang = session.me?.language, ["de", "en", "es"].contains(lang) {
                    settings.lang = lang
                }
                Haptics.success()
            } catch {
                errorText = (error as? APIError)?.message ?? L10n["error.generic"]
            }
        }
    }

    /// Guest mode. Without this the App Store listing — 12 screenshots in three
    /// locales — lands on a login wall, so someone who downloads the app to see
    /// what this is can see nothing at all. She reads the public impulses first
    /// and books the free introductory call from the same screen.
    private var guestDoor: some View {
        NavigationStack {
            NavigationLink { ImpulseView(guestMode: true) } label: {
                HStack(spacing: 10) {
                    Image(systemName: "book.closed").font(.system(size: 13))
                    Text(L10n["imp.guest.cta"])
                        .font(ANFont.text(13, weight: .medium))
                        .tracking(0.4)
                }
                .foregroundStyle(AN.clayDeep)
                .padding(.vertical, 12)
                .padding(.horizontal, 18)
                .overlay(Rectangle().strokeBorder(AN.goldHair, lineWidth: 1))
            }
        }
        .frame(height: 46)
    }

    private var languageRow: some View {
        HStack(spacing: 22) {
            ForEach(["de", "en", "es"], id: \.self) { lang in
                Button {
                    settings.lang = lang
                } label: {
                    Text(lang.uppercased())
                        .font(ANFont.text(12, weight: settings.lang == lang ? .semibold : .regular))
                        .tracking(1.2)
                        .foregroundStyle(settings.lang == lang ? AN.clay : AN.inkFaint)
                }
            }
        }
    }
}
