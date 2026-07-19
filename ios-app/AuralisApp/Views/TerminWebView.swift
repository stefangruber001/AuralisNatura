import SwiftUI
import WebKit
import UIKit

// MARK: - Booking tab (wraps the live /book wizard)

struct TerminWebView: View {
    @StateObject private var model = BookingWebModel()

    var body: some View {
        ZStack(alignment: .bottomTrailing) {
            if model.failed {
                VStack {
                    Spacer()
                    EmptyState(icon: "wifi.slash",
                               text: L10n["booking.offline"],
                               retry: { model.reload() })
                    Spacer()
                }
                .frame(maxWidth: .infinity)
            } else {
                WebViewContainer(model: model)

                if model.progress < 1 {
                    VStack(spacing: 0) {
                        ProgressView(value: max(model.progress, 0.05))
                            .progressViewStyle(.linear)
                            .tint(AN.clay)
                        Spacer()
                    }
                }

                menuButton
                    .padding(.trailing, 18)
                    .padding(.bottom, 24)
            }
        }
        .background(AN.paper.ignoresSafeArea())
        .sheet(isPresented: $model.showShare) {
            ShareSheet(items: model.shareItems)
        }
        .onAppear { model.loadIfNeeded() }
    }

    private var menuButton: some View {
        Menu {
            Button {
                model.reload()
            } label: {
                Label(L10n["booking.reload"], systemImage: "arrow.clockwise")
            }
            Button {
                UIApplication.shared.open(model.safariURL)
            } label: {
                Label(L10n["booking.safari"], systemImage: "safari")
            }
        } label: {
            Image(systemName: "ellipsis.circle.fill")
                .font(.system(size: 24, weight: .regular))
                .foregroundStyle(AN.forest)
                .padding(11)
                .background(AN.cream.opacity(0.92))
                .clipShape(Circle())
                .overlay(Circle().strokeBorder(AN.hairline, lineWidth: 1))
                .shadow(color: AN.ink.opacity(0.16), radius: 8, y: 3)
        }
    }
}

// MARK: - Web view model (owns the WKWebView)

final class BookingWebModel: NSObject, ObservableObject {
    // ?embed=1 tells the /book page to hide its own brand header — the app
    // already shows the Auralis bar above the web view (no double header).
    let bookingURL = URL(string: "https://api.auralisnatura.com/book?embed=1") ?? URL(fileURLWithPath: "/")
    // Opened in Safari (outside the app) → full standalone page, no embed trim.
    let safariURL = URL(string: "https://api.auralisnatura.com/book") ?? URL(fileURLWithPath: "/")

    @Published var progress: Double = 0
    @Published var failed = false
    @Published var showShare = false
    @Published var shareItems: [Any] = []

    private var progressObservation: NSKeyValueObservation?
    private var started = false

    private(set) lazy var webView: WKWebView = {
        let config = WKWebViewConfiguration()
        let controller = WKUserContentController()

        // navigator.share fallback → native share sheet.
        let script = """
        if (!window.navigator.share) {
          window.navigator.share = function (data) {
            window.webkit.messageHandlers.share.postMessage(data || {});
            return Promise.resolve();
          };
        }
        """
        controller.addUserScript(
            WKUserScript(source: script, injectionTime: .atDocumentStart, forMainFrameOnly: true)
        )
        controller.add(ShareMessageHandler(model: self), name: "share")
        config.userContentController = controller

        let webView = WKWebView(frame: .zero, configuration: config)
        webView.navigationDelegate = self
        webView.allowsBackForwardNavigationGestures = true
        webView.isOpaque = false
        webView.backgroundColor = UIColor(AN.paper)
        webView.scrollView.backgroundColor = UIColor(AN.paper)

        progressObservation = webView.observe(\.estimatedProgress, options: [.new]) { [weak self] view, _ in
            let value = view.estimatedProgress
            DispatchQueue.main.async { self?.progress = value }
        }
        return webView
    }()

    func loadIfNeeded() {
        guard !started else { return }
        started = true
        webView.load(URLRequest(url: bookingURL))
    }

    func reload() {
        failed = false
        progress = 0
        if webView.url == nil {
            webView.load(URLRequest(url: bookingURL))
        } else {
            webView.reload()
        }
    }

    func handleShare(_ body: Any) {
        var items: [Any] = []
        if let dict = body as? [String: Any] {
            if let title = dict["title"] as? String, !title.isEmpty { items.append(title) }
            if let text = dict["text"] as? String, !text.isEmpty { items.append(text) }
            if let urlString = dict["url"] as? String, let url = URL(string: urlString) {
                items.append(url)
            }
        }
        if items.isEmpty, let current = webView.url {
            items = [current]
        }
        shareItems = items
        showShare = true
    }
}

extension BookingWebModel: WKNavigationDelegate {
    func webView(_ webView: WKWebView,
                 didFailProvisionalNavigation navigation: WKNavigation!,
                 withError error: Error) {
        if (error as NSError).code != NSURLErrorCancelled {
            failed = true
        }
    }

    func webView(_ webView: WKWebView,
                 didFail navigation: WKNavigation!,
                 withError error: Error) {
        if (error as NSError).code != NSURLErrorCancelled {
            failed = true
        }
    }

    func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) {
        failed = false
        progress = 1
    }
}

/// Separate handler object: WKUserContentController retains its handlers
/// strongly, so the model is held weakly to avoid a retain cycle.
private final class ShareMessageHandler: NSObject, WKScriptMessageHandler {
    weak var model: BookingWebModel?

    init(model: BookingWebModel) {
        self.model = model
    }

    func userContentController(_ userContentController: WKUserContentController,
                               didReceive message: WKScriptMessage) {
        model?.handleShare(message.body)
    }
}

// MARK: - Representable

struct WebViewContainer: UIViewRepresentable {
    @ObservedObject var model: BookingWebModel

    func makeUIView(context: Context) -> WKWebView {
        model.webView
    }

    func updateUIView(_ webView: WKWebView, context: Context) {}
}
