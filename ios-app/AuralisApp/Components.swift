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

// MARK: - Status pill & KPI tile

struct StatusPill: View {
    let text: String
    let color: Color

    var body: some View {
        Text(text.uppercased()).anPill(color)
    }
}

struct KPITile: View {
    let value: String
    let label: String
    var accent: Color = AN.clay

    var body: some View {
        VStack(spacing: 4) {
            Text(value)
                .font(ANFont.display(26, weight: .semibold))
                .monospacedDigit()
                .foregroundStyle(accent)
                .lineLimit(1)
                .minimumScaleFactor(0.5)
            Text(label)
                .font(ANFont.text(11, weight: .medium))
                .tracking(0.4)
                .foregroundStyle(AN.inkSoft)
                .lineLimit(1)
                .minimumScaleFactor(0.7)
        }
        .frame(maxWidth: .infinity)
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
                        ZStack {
                            Circle()
                                .fill(isDone ? AN.sage : (isCurrent ? AN.clay : AN.paper2))
                                .frame(width: 22, height: 22)
                                .overlay(
                                    Circle().strokeBorder(
                                        isDone ? AN.sage : (isCurrent ? AN.clay : AN.hairline),
                                        lineWidth: 1)
                                )
                            if isDone {
                                Image(systemName: "checkmark")
                                    .font(.system(size: 10, weight: .bold))
                                    .foregroundStyle(AN.cream)
                            } else if isCurrent {
                                Circle().fill(AN.cream).frame(width: 6, height: 6)
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
