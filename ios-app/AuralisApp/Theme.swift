import SwiftUI
import UIKit

// MARK: - Colors

extension Color {
    init(hex: UInt) {
        self.init(.sRGB,
                  red: Double((hex >> 16) & 0xFF) / 255,
                  green: Double((hex >> 8) & 0xFF) / 255,
                  blue: Double(hex & 0xFF) / 255,
                  opacity: 1)
    }
}

/// Auralis Natura design tokens — warm-earth "cozy campfire" palette.
enum AN {
    static let ink        = Color(hex: 0x281F16)
    static let inkSoft    = Color(hex: 0x5C4A3A)
    static let inkFaint   = Color(hex: 0x75685A)   // was 0x6B5E4E — drifted from the CSS
    static let forest     = Color(hex: 0x3D2719)
    static let forestSoft = Color(hex: 0x5A3A22)   // top stop of the v2 dark band
    static let forestDeep = Color(hex: 0x221305)
    static let forest2    = Color(hex: 0x8A4A2A)   // cinnamon rust, LIGHT grounds only
    static let clay       = Color(hex: 0xA8492A)
    static let clayDeep   = Color(hex: 0x8F3D22)
    static let claySoft   = Color(hex: 0xC47A52)
    /// Pine marks POSITIVE things in the v2 report. New to the app — it exists in
    /// portal/lib/report_v2/*.html, not in design-system/dist/auralis.css.
    static let pine       = Color(hex: 0x3A4A2C)
    static let pineSoft   = Color(hex: 0x54663E)
    static let pineDeep   = Color(hex: 0x1C2513)
    static let gold       = Color(hex: 0xAD7A32)
    static let goldBright = Color(hex: 0xD6A84E)
    static let sage       = Color(hex: 0x927B4A)
    static let sageSoft   = Color(hex: 0xDAC79E)
    static let paper      = Color(hex: 0xF5EEE0)
    static let paper2     = Color(hex: 0xECE2CE)
    static let paper3     = Color(hex: 0xE3D6BC)
    static let cream      = Color(hex: 0xFBF6EB)
    static let ok         = Color(hex: 0x3F7B5A)
    static let warn       = Color(hex: 0xB0553F)
    static let hairline   = ink.opacity(0.14)
    static let goldHair   = gold.opacity(0.42)
}

// MARK: - Fonts (PostScript names are exact; registered at launch)

enum ANFont {
    enum Weight { case regular, medium, semibold }

    /// Fraunces — the editorial display voice.
    static func display(_ size: CGFloat,
                        weight: Weight = .regular,
                        italic: Bool = false,
                        relativeTo style: Font.TextStyle = .body) -> Font {
        if italic { return .custom("Fraunces-Italic", size: size, relativeTo: style) }
        switch weight {
        case .regular:            return .custom("Fraunces-Regular", size: size, relativeTo: style)
        case .medium, .semibold:  return .custom("Fraunces-SemiBold", size: size, relativeTo: style)
        }
    }

    /// Hanken Grotesk — quiet body & UI voice.
    static func text(_ size: CGFloat,
                     weight: Weight = .regular,
                     relativeTo style: Font.TextStyle = .body) -> Font {
        switch weight {
        case .regular:  return .custom("HankenGrotesk-Regular", size: size, relativeTo: style)
        case .medium:   return .custom("HankenGrotesk-Medium", size: size, relativeTo: style)
        case .semibold: return .custom("HankenGrotesk-SemiBold", size: size, relativeTo: style)
        }
    }
}

// MARK: - Card & field chrome (sharp geometry — radius 0 is the brand)

private struct ANCardModifier: ViewModifier {
    let background: Color
    func body(content: Content) -> some View {
        content
            .background(background)
            .overlay(Rectangle().strokeBorder(AN.hairline, lineWidth: 1))
            .shadow(color: AN.ink.opacity(0.06), radius: 10, x: 0, y: 4)
    }
}

private struct ANFieldChromeModifier: ViewModifier {
    func body(content: Content) -> some View {
        content
            .background(Color.white)
            .overlay(Rectangle().strokeBorder(AN.hairline, lineWidth: 1))
            .overlay(alignment: .leading) { Rectangle().fill(AN.gold).frame(width: 3) }
    }
}

extension View {
    func anCard(_ background: Color = AN.cream) -> some View {
        modifier(ANCardModifier(background: background))
    }
    func anFieldChrome() -> some View {
        modifier(ANFieldChromeModifier())
    }
}

// MARK: - Button styles

struct ANPrimaryButtonStyle: ButtonStyle {
    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(ANFont.text(16, weight: .semibold))
            .foregroundStyle(AN.cream)
            .frame(maxWidth: .infinity)
            .padding(.vertical, 15)
            .background(configuration.isPressed ? AN.clayDeep : AN.clay)
            .scaleEffect(configuration.isPressed ? 0.985 : 1)
            .animation(.easeOut(duration: 0.12), value: configuration.isPressed)
    }
}

struct ANGoldButtonStyle: ButtonStyle {
    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(ANFont.text(16, weight: .semibold))
            .foregroundStyle(AN.forestDeep)
            .frame(maxWidth: .infinity)
            .padding(.vertical, 15)
            .background(
                LinearGradient(colors: [AN.goldBright, AN.gold],
                               startPoint: .top, endPoint: .bottom)
            )
            .scaleEffect(configuration.isPressed ? 0.985 : 1)
            .animation(.easeOut(duration: 0.12), value: configuration.isPressed)
    }
}

struct ANOutlineButtonStyle: ButtonStyle {
    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(ANFont.text(15, weight: .semibold))
            .foregroundStyle(AN.forest)
            .padding(.horizontal, 20)
            .padding(.vertical, 12)
            .background(configuration.isPressed ? AN.paper2 : Color.clear)
            .overlay(Rectangle().strokeBorder(AN.ink.opacity(0.26), lineWidth: 1))
            .scaleEffect(configuration.isPressed ? 0.985 : 1)
            .animation(.easeOut(duration: 0.12), value: configuration.isPressed)
    }
}

extension ButtonStyle where Self == ANPrimaryButtonStyle {
    static var anPrimary: ANPrimaryButtonStyle { .init() }
}
extension ButtonStyle where Self == ANGoldButtonStyle {
    static var anGold: ANGoldButtonStyle { .init() }
}
extension ButtonStyle where Self == ANOutlineButtonStyle {
    static var anOutline: ANOutlineButtonStyle { .init() }
}

// MARK: - Pill

extension Text {
    /// Small uppercase pill — one accent per card, used sparingly.
    func anPill(_ color: Color, filled: Bool = false) -> some View {
        self
            .font(ANFont.text(11, weight: .semibold))
            .tracking(1.1)
            .foregroundStyle(filled ? AN.cream : color)
            .padding(.horizontal, 10)
            .padding(.vertical, 5)
            .background(filled ? color : color.opacity(0.10))
            .overlay(Rectangle().strokeBorder(color.opacity(0.4), lineWidth: 1))
    }
}

// MARK: - Haptics

enum Haptics {
    static func tap() {
        UIImpactFeedbackGenerator(style: .light).impactOccurred()
    }
    static func success() {
        UINotificationFeedbackGenerator().notificationOccurred(.success)
    }
    static func warning() {
        UINotificationFeedbackGenerator().notificationOccurred(.warning)
    }
}
