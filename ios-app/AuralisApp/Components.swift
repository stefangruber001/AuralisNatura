import SwiftUI
import UIKit

// MARK: - Brand bar

struct BrandBar: View {
    var body: some View {
        VStack(spacing: 0) {
            HStack(spacing: 12) {
                Image("Emblem")
                    .resizable()
                    .scaledToFit()
                    .frame(width: 30, height: 30)
                VStack(alignment: .leading, spacing: 1) {
                    Text("Auralis Natura")
                        .font(ANFont.display(19, weight: .semibold))
                        .foregroundStyle(AN.forest)
                    Text(L10n["brand.slogan"])
                        .font(ANFont.text(11))
                        .foregroundStyle(AN.inkSoft)
                        .lineLimit(1)
                        .minimumScaleFactor(0.8)
                }
                Spacer()
                SparkDots()
            }
            .padding(.horizontal, 20)
            .padding(.top, 8)
            .padding(.bottom, 10)
            Rectangle().fill(AN.goldHair).frame(height: 1)
        }
        .background(AN.paper)
    }
}

// MARK: - Section header ("FIG. 0X — TITLE" + gold rule)

struct SectionHeader: View {
    let fig: String
    let title: String

    var body: some View {
        HStack(spacing: 10) {
            Text("\(fig) — \(title.uppercased())")
                .font(ANFont.text(10, weight: .semibold))
                .tracking(1.6)
                .foregroundStyle(AN.clay)
            Rectangle().fill(AN.gold).frame(width: 34, height: 1)
            Spacer(minLength: 0)
        }
    }
}

// MARK: - Spark ornament

struct SparkDots: View {
    var body: some View {
        HStack(spacing: 4) {
            Circle().fill(AN.clay).frame(width: 5, height: 5)
            Circle().fill(AN.gold).frame(width: 5, height: 5)
            Circle().fill(AN.sage).frame(width: 5, height: 5)
        }
        .accessibilityHidden(true)
    }
}

// MARK: - Status pill

struct StatusPill: View {
    let text: String
    let color: Color

    var body: some View {
        Text(text.uppercased()).anPill(color)
    }
}

// MARK: - Text field

struct ANTextField: View {
    let label: String
    @Binding var text: String
    var secure = false
    var uppercase = false
    var contentType: UITextContentType?

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text(label)
                .font(ANFont.text(12, weight: .semibold))
                .tracking(0.8)
                .foregroundStyle(AN.inkSoft)
            Group {
                if secure {
                    SecureField("", text: $text)
                } else {
                    TextField("", text: $text)
                }
            }
            .font(ANFont.text(16))
            .foregroundStyle(AN.ink)
            // the caption above is a separate Text, so without this VoiceOver
            // announces a bare "text field" with no name
            .accessibilityLabel(label)
            .textInputAutocapitalization(uppercase ? .characters : .never)
            .autocorrectionDisabled()
            .textContentType(contentType)
            .padding(.horizontal, 14)
            .frame(minHeight: 48)
            .anFieldChrome()
            .onChange(of: text) { _, newValue in
                if uppercase {
                    let up = newValue.uppercased()
                    if up != newValue { text = up }
                }
            }
        }
    }
}

// MARK: - Empty state

struct EmptyState: View {
    let icon: String
    let text: String
    var retry: (() -> Void)?

    var body: some View {
        VStack(spacing: 14) {
            Image(systemName: icon)
                .font(.system(size: 30, weight: .light))
                .foregroundStyle(AN.inkFaint)
            Text(text)
                .font(ANFont.text(14))
                .foregroundStyle(AN.inkSoft)
                .multilineTextAlignment(.center)
            if let retry {
                Button(L10n["common.retry"]) {
                    Haptics.tap()
                    retry()
                }
                .buttonStyle(.anOutline)
                .padding(.top, 4)
            }
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, 36)
        .padding(.horizontal, 24)
    }
}

// MARK: - Skeleton shimmer

struct SkeletonRow: View {
    var height: CGFloat = 72
    @State private var offset: CGFloat = -240

    var body: some View {
        Rectangle()
            .fill(AN.paper2)
            .overlay(
                LinearGradient(colors: [.clear, Color.white.opacity(0.5), .clear],
                               startPoint: .leading, endPoint: .trailing)
                .frame(width: 140)
                .offset(x: offset)
            )
            .frame(height: height)
            .frame(maxWidth: .infinity)
            .clipped()
            .onAppear {
                withAnimation(.linear(duration: 1.15).repeatForever(autoreverses: false)) {
                    offset = 500
                }
            }
    }
}

// MARK: - Toast

@MainActor
final class ToastStore: ObservableObject {
    enum Kind { case ok, error }

    struct Toast: Equatable {
        let text: String
        let kind: Kind
    }

    @Published var current: Toast?
    private var dismissTask: Task<Void, Never>?

    func show(_ text: String, kind: Kind = .ok) {
        dismissTask?.cancel()
        withAnimation(.spring(duration: 0.3)) {
            current = Toast(text: text, kind: kind)
        }
        dismissTask = Task { [weak self] in
            try? await Task.sleep(for: .seconds(2.6))
            guard !Task.isCancelled else { return }
            withAnimation(.easeOut(duration: 0.25)) {
                self?.current = nil
            }
        }
    }
}

struct ToastOverlay: View {
    @EnvironmentObject private var toasts: ToastStore

    var body: some View {
        VStack {
            Spacer()
            if let toast = toasts.current {
                HStack(spacing: 8) {
                    Image(systemName: toast.kind == .ok
                          ? "checkmark.circle.fill"
                          : "exclamationmark.triangle.fill")
                        .font(.system(size: 15, weight: .medium))
                    Text(toast.text)
                        .font(ANFont.text(14, weight: .medium))
                        .multilineTextAlignment(.leading)
                }
                .foregroundStyle(AN.cream)
                .padding(.horizontal, 16)
                .padding(.vertical, 12)
                .background(toast.kind == .ok ? AN.ok : AN.warn)
                .shadow(color: AN.ink.opacity(0.2), radius: 12, y: 4)
                .padding(.horizontal, 24)
                .padding(.bottom, 28)
                .transition(.move(edge: .bottom).combined(with: .opacity))
            }
        }
        .animation(.spring(duration: 0.3), value: toasts.current)
        .allowsHitTesting(false)
    }
}

// MARK: - Progress band (the Home hero)

/// Where she stands, on the brand's premium surface: the warm dark band with the
/// seal bleeding off the edge (print decision 2), amber gold as the structural
/// accent, one named next action.
///
/// The colours carry meaning and nothing else: **amber solid = done**, **amber
/// half = in flight right now**, **cream 12% = still ahead**. Pine reads as
/// "good" on the report's light pages but disappears on dark brown, so on this
/// surface amber does that job.
///
/// Motivation here is honest by construction — the fraction is the server's real
/// stage, the phrasing counts what is *done* rather than what is missing, and
/// there is exactly one call to action, never a deadline or a scarcity claim.
struct ProgressBand: View {
    let done: Int                     // completed steps, 0…total
    let total: Int
    let milestone: String             // where she stands, in words
    var actionTitle: String? = nil    // the ONE next action (nil = nothing to do)
    var action: (() -> Void)? = nil

    private var complete: Bool { done >= total }

    var body: some View {
        VStack(alignment: .leading, spacing: 18) {
            HStack(alignment: .top, spacing: 12) {
                VStack(alignment: .leading, spacing: 7) {
                    Text(L10n["home.progress.kicker"])
                        .font(ANFont.text(11, weight: .semibold))
                        .tracking(1.7)
                        .foregroundStyle(AN.goldBright)
                    Text(L10n[complete ? "home.progress.complete" : "home.progress.title"])
                        .font(ANFont.display(21, weight: .semibold))
                        .foregroundStyle(AN.cream)
                        .fixedSize(horizontal: false, vertical: true)
                }
                Spacer(minLength: 8)
                HStack(alignment: .lastTextBaseline, spacing: 0) {
                    Text("\(min(done, total))")
                        .font(ANFont.display(38, weight: .semibold))
                        .foregroundStyle(AN.goldBright)
                    Text("/\(total)")
                        .font(ANFont.display(18))
                        .foregroundStyle(AN.cream.opacity(0.5))
                }
                .monospacedDigit()
                .accessibilityLabel(L10n.f("home.progress.a11y", "\(min(done, total))", "\(total)"))
            }

            HStack(spacing: 5) {
                ForEach(0..<max(total, 1), id: \.self) { i in
                    let isDone = i < done
                    let isNow = i == done
                    Rectangle()
                        .fill(isDone ? AN.goldBright
                              : (isNow ? AN.goldBright.opacity(0.45) : AN.cream.opacity(0.12)))
                        .frame(height: 5)
                        .overlay(alignment: .leading) {
                            if isNow {
                                Rectangle().fill(AN.goldBright).frame(width: 2)
                            }
                        }
                }
            }
            .accessibilityHidden(true)

            Text(milestone)
                .font(ANFont.text(14))
                .foregroundStyle(AN.cream.opacity(0.78))
                .fixedSize(horizontal: false, vertical: true)

            if let actionTitle, let action {
                Button {
                    Haptics.tap()
                    action()
                } label: {
                    Text(actionTitle)
                }
                .buttonStyle(.anGold)
            }
        }
        .padding(22)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background {
            LinearGradient(colors: [AN.forestSoft, AN.forest, AN.forestDeep],
                           startPoint: .topLeading, endPoint: .bottomTrailing)
        }
        .background(alignment: .bottomTrailing) {
            Image("Emblem")
                .resizable()
                .scaledToFit()
                .frame(width: 210, height: 210)
                .opacity(0.09)
                .offset(x: 72, y: 68)
                .allowsHitTesting(false)
        }
        .clipped()
        .overlay(Rectangle().strokeBorder(AN.goldHair, lineWidth: 1))
        .shadow(color: AN.ink.opacity(0.14), radius: 18, x: 0, y: 8)
    }
}

// MARK: - Locked card (the client area, seen from outside)

/// What opens with access, and the one way in.
///
/// It names what is inside rather than what is withheld, and carries a single
/// action — the free introductory call. No countdown, no "places left", no
/// nagging: the engagement rules in CLAUDE.md apply to a prospect exactly as
/// they apply to a client.
struct LockedCard: View {
    let title: String
    let sub: String
    let items: [String]
    let ctaTitle: String
    let action: () -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            HStack(spacing: 10) {
                Image(systemName: "lock")
                    .font(.system(size: 12, weight: .medium))
                    .foregroundStyle(AN.gold)
                Text(L10n["guest.locked.kicker"].uppercased())
                    .font(ANFont.text(10, weight: .semibold))
                    .tracking(1.6)
                    .foregroundStyle(AN.gold)
                Rectangle().fill(AN.gold).frame(width: 26, height: 1)
                Spacer(minLength: 0)
            }
            Text(title)
                .font(ANFont.display(20, weight: .semibold))
                .foregroundStyle(AN.forest)
                .fixedSize(horizontal: false, vertical: true)
            Text(sub)
                .font(ANFont.text(13))
                .foregroundStyle(AN.inkSoft)
                .fixedSize(horizontal: false, vertical: true)
            VStack(alignment: .leading, spacing: 8) {
                ForEach(items, id: \.self) { item in
                    HStack(alignment: .top, spacing: 10) {
                        Rectangle()
                            .fill(AN.sage)
                            .frame(width: 6, height: 6)
                            .padding(.top, 6)
                        Text(item)
                            .font(ANFont.text(14))
                            .foregroundStyle(AN.ink)
                            .fixedSize(horizontal: false, vertical: true)
                    }
                }
            }
            .padding(.top, 2)
            // Outline, not clay: the screen's one primary button belongs to the
            // main call-to-action above (print decision 3 — clay is an accent,
            // one primary per view). The action still sits where it is needed.
            Button {
                Haptics.tap()
                action()
            } label: {
                Text(ctaTitle).frame(maxWidth: .infinity)
            }
            .buttonStyle(.anOutline)
            .padding(.top, 4)
        }
        .padding(20)
        .frame(maxWidth: .infinity, alignment: .leading)
        .anCard()
    }
}

// MARK: - Self-assessment scale row

/// One 1–5 self-rating, in the printed report's own vocabulary (five segments,
/// status-coloured): pine = strong, sage = middling, clay = strained. She sees
/// the same rows in her PDF and in the portal, so the three read as one system.
///
/// A rating is never called a score and never summed into one number — §2: this
/// is her own self-assessment, not a health measurement.
struct ScaleRow: View {
    let label: String
    let value: Int

    /// EVERY scale reads higher-is-better, stress included — it is asked as
    /// "Stressbalance" (1 = low balance … 5 = very good) on all three intake
    /// surfaces. Same reading as render._status().
    ///
    /// Shared with the intake input so the colour a client picks is the colour
    /// she later sees in her report — one scale learnt once, three surfaces.
    static func tone(for value: Int) -> Color {
        value >= 4 ? AN.pine : (value >= 3 ? AN.sage : AN.clay)
    }
    private var status: Color { ScaleRow.tone(for: value) }

    var body: some View {
        let v = max(1, min(5, value))
        HStack(spacing: 12) {
            Text(label.uppercased())
                .font(ANFont.text(11, weight: .semibold))
                .tracking(1.1)
                .foregroundStyle(AN.inkSoft)
                .frame(width: 92, alignment: .leading)
                .lineLimit(1)
                .minimumScaleFactor(0.75)
            HStack(spacing: 5) {
                ForEach(0..<5, id: \.self) { i in
                    Rectangle()
                        .fill(i < v ? status : AN.paper2)
                        .overlay(Rectangle().strokeBorder(
                            i < v ? status : AN.hairline, lineWidth: 1))
                        .frame(height: 9)
                }
            }
            HStack(alignment: .lastTextBaseline, spacing: 1) {
                Text("\(v)")
                    .font(ANFont.display(15, weight: .medium))
                    .foregroundStyle(AN.ink)
                Text(String(L10n.f("unit.of5", "").dropFirst()))
                    .font(ANFont.text(11))
                    .foregroundStyle(AN.inkFaint)
            }
            .monospacedDigit()
        }
        .accessibilityElement(children: .ignore)
        .accessibilityLabel("\(label): \(v)/5")
    }
}

// MARK: - Journey timeline

struct JourneyTimeline: View {
    /// Completed steps, 0…4.
    let done: Int
    var compact = false

    private let stepKeys = ["journey.step1", "journey.step2", "journey.step3", "journey.step4"]

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            ForEach(0..<4, id: \.self) { index in
                let key = stepKeys[index]
                let number = index + 1
                let isDone = number <= done
                let isCurrent = number == done + 1

                HStack(alignment: .top, spacing: 14) {
                    VStack(spacing: 0) {
                        // square markers, pine for done — the report's own
                        // vocabulary, and radius 0 is the brand's structure
                        ZStack {
                            Rectangle()
                                .fill(isDone ? AN.pine : (isCurrent ? AN.clay : AN.paper2))
                                .frame(width: 22, height: 22)
                                .overlay(
                                    Rectangle().strokeBorder(
                                        isDone ? AN.pineDeep : (isCurrent ? AN.clay : AN.hairline),
                                        lineWidth: 1)
                                )
                            if isDone {
                                Image(systemName: "checkmark")
                                    .font(.system(size: 10, weight: .bold))
                                    .foregroundStyle(AN.cream)
                            } else if isCurrent {
                                Rectangle().fill(AN.cream).frame(width: 6, height: 6)
                            }
                        }
                        if index < stepKeys.count - 1 {
                            Rectangle()
                                .fill(AN.hairline)
                                .frame(width: 1)
                                .frame(minHeight: compact ? 16 : 26)
                        }
                    }
                    VStack(alignment: .leading, spacing: 2) {
                        Text(L10n[key])
                            .font(ANFont.text(15, weight: isCurrent ? .semibold : .medium))
                            .foregroundStyle(isCurrent ? AN.ink : (isDone ? AN.inkSoft : AN.inkFaint))
                        if !compact {
                            Text(L10n[key + ".sub"])
                                .font(ANFont.text(12))
                                .foregroundStyle(AN.inkFaint)
                                .fixedSize(horizontal: false, vertical: true)
                        }
                    }
                    .padding(.bottom, index < stepKeys.count - 1 ? 14 : 0)
                    Spacer(minLength: 0)
                }
            }
        }
    }
}

// MARK: - Share sheet

struct ShareSheet: UIViewControllerRepresentable {
    let items: [Any]

    func makeUIViewController(context: Context) -> UIActivityViewController {
        UIActivityViewController(activityItems: items, applicationActivities: nil)
    }

    func updateUIViewController(_ controller: UIActivityViewController, context: Context) {}
}
