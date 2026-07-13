import SwiftUI

/// 4-step intake sheet, matching the web intake (POST /api/intake).
struct IntakeFlow: View {
    @EnvironmentObject private var session: SessionStore
    @EnvironmentObject private var settings: SettingsStore
    @EnvironmentObject private var toasts: ToastStore
    @Environment(\.dismiss) private var dismiss

    @State private var step = 0
    @State private var goal = ""
    @State private var whyNow = ""
    @State private var energy = 3
    @State private var sleep = 3
    @State private var stress = 3
    @State private var digestion = 3
    @State private var flags: Set<String> = []
    @State private var consentCoaching = false
    @State private var consentGDPR = false
    @State private var sending = false
    @State private var sent = false
    @FocusState private var editorFocused: Bool

    private static let flagKeys = ["weight_loss", "chest_pain", "fainting", "self_harm", "none"]

    var body: some View {
        NavigationStack {
            Group {
                if sent {
                    successView
                } else {
                    VStack(spacing: 0) {
                        progressDots
                            .padding(.top, 14)
                            .padding(.bottom, 6)
                        ScrollView {
                            stepContent
                                .padding(20)
                        }
                        .scrollDismissesKeyboard(.interactively)
                        footerBar
                    }
                }
            }
            .background(AN.paper.ignoresSafeArea())
            .navigationTitle(L10n["intake.title"])
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                if !sent {
                    ToolbarItem(placement: .topBarTrailing) {
                        Button {
                            dismiss()
                        } label: {
                            Image(systemName: "xmark")
                                .font(.system(size: 14, weight: .semibold))
                                .foregroundStyle(AN.inkSoft)
                        }
                        .disabled(sending)
                    }
                }
                ToolbarItemGroup(placement: .keyboard) {
                    Spacer()
                    Button(L10n["common.done"]) { editorFocused = false }
                        .font(ANFont.text(15, weight: .semibold))
                        .foregroundStyle(AN.clay)
                }
            }
        }
        .interactiveDismissDisabled(sending)
    }

    // MARK: Progress dots

    private var progressDots: some View {
        HStack(spacing: 8) {
            ForEach(0..<4, id: \.self) { i in
                Circle()
                    .fill(i < step ? AN.sage : (i == step ? AN.clay : AN.paper2))
                    .overlay(Circle().strokeBorder(i <= step ? Color.clear : AN.hairline, lineWidth: 1))
                    .frame(width: 8, height: 8)
            }
        }
    }

    // MARK: Steps

    @ViewBuilder
    private var stepContent: some View {
        switch step {
        case 0:  stepGoal
        case 1:  stepScales
        case 2:  stepSafety
        default: stepReview
        }
    }

    private func stepTitle(_ title: String, sub: String) -> some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(title)
                .font(ANFont.display(22, weight: .semibold))
                .foregroundStyle(AN.ink)
            Text(sub)
                .font(ANFont.text(13))
                .foregroundStyle(AN.inkSoft)
                .fixedSize(horizontal: false, vertical: true)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }

    // Step 1 — goal

    private var stepGoal: some View {
        VStack(alignment: .leading, spacing: 20) {
            stepTitle(L10n["intake.step1.title"], sub: L10n["intake.step1.sub"])
            editor(label: L10n["intake.goal.label"], text: $goal)
            editor(label: L10n["intake.whyNow.label"], text: $whyNow)
        }
    }

    private func editor(label: String, text: Binding<String>) -> some View {
        VStack(alignment: .leading, spacing: 6) {
            Text(label)
                .font(ANFont.text(12, weight: .semibold))
                .tracking(0.8)
                .foregroundStyle(AN.inkSoft)
            TextEditor(text: text)
                .font(ANFont.text(16))
                .foregroundStyle(AN.ink)
                .focused($editorFocused)
                .scrollContentBackground(.hidden)
                .padding(.horizontal, 10)
                .padding(.vertical, 6)
                .frame(minHeight: 120)
                .anFieldChrome()
        }
    }

    // Step 2 — self-assessment scales

    private var stepScales: some View {
        VStack(alignment: .leading, spacing: 24) {
            stepTitle(L10n["intake.step2.title"], sub: L10n["intake.step2.sub"])
            scaleRow(L10n["intake.scale.energy"], value: $energy)
            scaleRow(L10n["intake.scale.sleep"], value: $sleep)
            scaleRow(L10n["intake.scale.stress"], value: $stress)
            scaleRow(L10n["intake.scale.digestion"], value: $digestion)
        }
    }

    private func scaleRow(_ label: String, value: Binding<Int>) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            Text(label)
                .font(ANFont.text(15, weight: .semibold))
                .foregroundStyle(AN.ink)
            HStack(spacing: 6) {
                ForEach(1...5, id: \.self) { n in
                    Button {
                        Haptics.tap()
                        value.wrappedValue = n
                    } label: {
                        Text("\(n)")
                            .font(ANFont.text(16, weight: .semibold))
                            .monospacedDigit()
                            .frame(maxWidth: .infinity)
                            .frame(height: 44)
                            .foregroundStyle(value.wrappedValue == n ? AN.cream : AN.ink)
                            .background(value.wrappedValue == n ? AN.forest : Color.white)
                            .overlay(Rectangle().strokeBorder(AN.hairline, lineWidth: 1))
                    }
                    .buttonStyle(.plain)
                }
            }
            HStack {
                Text(L10n["intake.scale.low"])
                Spacer()
                Text(L10n["intake.scale.high"])
            }
            .font(ANFont.text(11))
            .foregroundStyle(AN.inkFaint)
        }
    }

    // Step 3 — safety & consent

    private var stepSafety: some View {
        VStack(alignment: .leading, spacing: 20) {
            stepTitle(L10n["intake.step3.title"], sub: L10n["intake.safety.info"])

            VStack(spacing: 0) {
                ForEach(Self.flagKeys, id: \.self) { key in
                    flagRow(key)
                    if key != Self.flagKeys.last {
                        Rectangle().fill(AN.hairline).frame(height: 1).padding(.leading, 14)
                    }
                }
            }
            .anCard()

            if hasRedFlag {
                Text(L10n["intake.flag.notice"])
                    .font(ANFont.text(13))
                    .foregroundStyle(AN.warn)
                    .fixedSize(horizontal: false, vertical: true)
                    .padding(14)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .background(AN.warn.opacity(0.08))
                    .overlay(Rectangle().strokeBorder(AN.warn.opacity(0.35), lineWidth: 1))
            }

            VStack(spacing: 14) {
                consentRow(L10n["intake.consent.coaching"], isOn: $consentCoaching)
                consentRow(L10n["intake.consent.gdpr"], isOn: $consentGDPR)
            }
        }
    }

    private func flagRow(_ key: String) -> some View {
        let selected = flags.contains(key)
        return Button {
            toggleFlag(key)
        } label: {
            HStack(spacing: 12) {
                Image(systemName: selected ? "checkmark.square.fill" : "square")
                    .font(.system(size: 20, weight: .light))
                    .foregroundStyle(selected ? AN.forest : AN.inkFaint)
                Text(L10n[flagL10nKey(key)])
                    .font(ANFont.text(14))
                    .foregroundStyle(AN.ink)
                    .multilineTextAlignment(.leading)
                Spacer()
            }
            .padding(14)
            .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
    }

    private func flagL10nKey(_ key: String) -> String {
        switch key {
        case "weight_loss": return "intake.flag.weight"
        case "chest_pain":  return "intake.flag.chest"
        case "fainting":    return "intake.flag.faint"
        case "self_harm":   return "intake.flag.selfharm"
        default:            return "intake.flag.none"
        }
    }

    private func toggleFlag(_ key: String) {
        Haptics.tap()
        if key == "none" {
            flags = flags.contains("none") ? [] : ["none"]
        } else {
            flags.remove("none")
            if flags.contains(key) {
                flags.remove(key)
            } else {
                flags.insert(key)
            }
        }
    }

    private var hasRedFlag: Bool {
        !flags.isEmpty && !flags.contains("none")
    }

    private func consentRow(_ text: String, isOn: Binding<Bool>) -> some View {
        Toggle(isOn: isOn) {
            Text(text)
                .font(ANFont.text(13))
                .foregroundStyle(AN.ink)
                .fixedSize(horizontal: false, vertical: true)
        }
        .tint(AN.forest)
        .padding(14)
        .anCard()
    }

    // Step 4 — review & send

    private var stepReview: some View {
        VStack(alignment: .leading, spacing: 16) {
            stepTitle(L10n["intake.step4.title"], sub: L10n["intake.step4.sub"])

            reviewBlock(L10n["intake.review.goal"]) {
                Text(goal.trimmingCharacters(in: .whitespacesAndNewlines))
                    .font(ANFont.text(14))
                    .foregroundStyle(AN.ink)
                    .fixedSize(horizontal: false, vertical: true)
            }

            reviewBlock(L10n["intake.review.scales"]) {
                VStack(alignment: .leading, spacing: 6) {
                    reviewScale(L10n["intake.scale.energy"], energy)
                    reviewScale(L10n["intake.scale.sleep"], sleep)
                    reviewScale(L10n["intake.scale.stress"], stress)
                    reviewScale(L10n["intake.scale.digestion"], digestion)
                }
            }

            reviewBlock(L10n["intake.review.flags"]) {
                if hasRedFlag {
                    VStack(alignment: .leading, spacing: 4) {
                        ForEach(Self.flagKeys.filter { flags.contains($0) && $0 != "none" }, id: \.self) { key in
                            Text("— " + L10n[flagL10nKey(key)])
                                .font(ANFont.text(14))
                                .foregroundStyle(AN.warn)
                        }
                    }
                } else {
                    Text(L10n["intake.review.flags.none"])
                        .font(ANFont.text(14))
                        .foregroundStyle(AN.inkSoft)
                }
            }

            reviewBlock(L10n["intake.review.consent"]) {
                Text(L10n["intake.review.consent.given"])
                    .font(ANFont.text(14))
                    .foregroundStyle(AN.ok)
            }
        }
    }

    private func reviewBlock(_ title: String, @ViewBuilder content: () -> some View) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            Text(title.uppercased())
                .font(ANFont.text(11, weight: .semibold))
                .tracking(1.2)
                .foregroundStyle(AN.clay)
            content()
        }
        .padding(14)
        .frame(maxWidth: .infinity, alignment: .leading)
        .anCard()
    }

    private func reviewScale(_ label: String, _ value: Int) -> some View {
        HStack {
            Text(label)
                .font(ANFont.text(14))
                .foregroundStyle(AN.ink)
            Spacer()
            Text("\(value)/5")
                .font(ANFont.text(14, weight: .semibold))
                .monospacedDigit()
                .foregroundStyle(AN.inkSoft)
        }
    }

    // MARK: Footer

    private var footerBar: some View {
        HStack(spacing: 12) {
            if step > 0 {
                Button(L10n["common.back"]) {
                    Haptics.tap()
                    editorFocused = false
                    withAnimation(.easeInOut(duration: 0.2)) { step -= 1 }
                }
                .buttonStyle(.anOutline)
                .disabled(sending)
            }
            Button {
                advance()
            } label: {
                if sending {
                    ProgressView().tint(AN.cream)
                } else {
                    Text(step == 3 ? L10n["common.send"] : L10n["common.next"])
                }
            }
            .buttonStyle(.anPrimary)
            .disabled(!canAdvance || sending)
        }
        .padding(16)
        .background(AN.cream)
        .overlay(alignment: .top) {
            Rectangle().fill(AN.hairline).frame(height: 1)
        }
    }

    private var canAdvance: Bool {
        switch step {
        case 0:  return !goal.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
        case 1:  return true
        case 2:  return !flags.isEmpty && consentCoaching && consentGDPR
        default: return consentCoaching && consentGDPR
        }
    }

    private func advance() {
        Haptics.tap()
        editorFocused = false
        if step < 3 {
            withAnimation(.easeInOut(duration: 0.2)) { step += 1 }
        } else {
            send()
        }
    }

    // MARK: Send

    private func send() {
        sending = true
        let body = IntakeBody(
            goal: goal.trimmingCharacters(in: .whitespacesAndNewlines),
            whyNow: whyNow.trimmingCharacters(in: .whitespacesAndNewlines),
            b: IntakeBody.Scales(energy: energy, sleep: sleep, stress: stress, digestion: digestion),
            language: session.me?.language ?? settings.lang,
            redFlags: Array(flags),
            consent: IntakeBody.Consent(coachingNotMedical: true, gdprHealthData: true)
        )
        Task { @MainActor in
            do {
                let _: OkResponse = try await APIClient.shared.post("/api/intake", body: body)
                Haptics.success()
                sent = true
                await session.refreshMe()
            } catch APIError.conflict {
                toasts.show(L10n["intake.conflict"])
                await session.refreshMe()
                dismiss()
            } catch {
                toasts.show((error as? APIError)?.message ?? L10n["error.generic"], kind: .error)
            }
            sending = false
        }
    }

    // MARK: Success

    private var successView: some View {
        VStack(spacing: 18) {
            Spacer()
            ZStack {
                Circle().fill(AN.sage).frame(width: 84, height: 84)
                Image(systemName: "checkmark")
                    .font(.system(size: 34, weight: .semibold))
                    .foregroundStyle(AN.cream)
            }
            Text(L10n["intake.success.title"])
                .font(ANFont.display(24, weight: .semibold))
                .foregroundStyle(AN.ink)
            Text(L10n["intake.success.sub"])
                .font(ANFont.text(14))
                .foregroundStyle(AN.inkSoft)
                .multilineTextAlignment(.center)
                .padding(.horizontal, 32)
            Spacer()
            Button(L10n["common.close"]) {
                dismiss()
            }
            .buttonStyle(.anPrimary)
            .padding(.horizontal, 20)
            .padding(.bottom, 24)
        }
    }
}
