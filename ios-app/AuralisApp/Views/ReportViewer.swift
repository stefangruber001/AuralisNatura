import SwiftUI
import PDFKit

/// Fetches a short-lived token, downloads the report PDF and shows it.
struct ReportViewer: View {
    enum LoadState {
        case loading
        case loaded(PDFDocument, URL)
        case failed
    }

    @State private var state: LoadState = .loading
    @State private var showShare = false

    var body: some View {
        Group {
            switch state {
            case .loading:
                VStack(spacing: 14) {
                    ProgressView().tint(AN.clay)
                    Text(L10n["report.loading"])
                        .font(ANFont.text(14))
                        .foregroundStyle(AN.inkSoft)
                }
                .frame(maxWidth: .infinity, maxHeight: .infinity)
            case .loaded(let document, _):
                PDFKitView(document: document)
            case .failed:
                VStack {
                    Spacer()
                    EmptyState(icon: "exclamationmark.triangle",
                               text: L10n["report.error"],
                               retry: { Task { await load() } })
                    Spacer()
                }
                .frame(maxWidth: .infinity)
            }
        }
        .background(AN.paper.ignoresSafeArea())
        .navigationTitle(L10n["report.title"])
        .navigationBarTitleDisplayMode(.inline)
        .toolbar(.visible, for: .navigationBar)
        .toolbar {
            ToolbarItem(placement: .topBarTrailing) {
                if case .loaded = state {
                    Button {
                        Haptics.tap()
                        showShare = true
                    } label: {
                        Image(systemName: "square.and.arrow.up")
                            .foregroundStyle(AN.clay)
                    }
                }
            }
        }
        .sheet(isPresented: $showShare) {
            if case .loaded(_, let url) = state {
                ShareSheet(items: [url])
            }
        }
        .task {
            if case .loading = state {
                await load()
            }
        }
    }

    @MainActor
    private func load() async {
        state = .loading
        do {
            let tokenResponse: ReportTokenResponse = try await APIClient.shared.post(
                "/api/my/report-token", body: EmptyBody())
            let data = try await APIClient.shared.getRaw(
                "/api/my/report",
                query: [URLQueryItem(name: "token", value: tokenResponse.token)])
            guard let document = PDFDocument(data: data) else {
                state = .failed
                return
            }
            let fileURL = FileManager.default.temporaryDirectory
                .appendingPathComponent(L10n["report.filename"])
            try? data.write(to: fileURL, options: .atomic)
            state = .loaded(document, fileURL)
        } catch {
            if !(error is CancellationError) {
                state = .failed
            }
        }
    }
}

// MARK: - PDFKit wrapper

struct PDFKitView: UIViewRepresentable {
    let document: PDFDocument

    func makeUIView(context: Context) -> PDFView {
        let view = PDFView()
        view.autoScales = true
        view.displayMode = .singlePageContinuous
        view.displayDirection = .vertical
        view.backgroundColor = UIColor(AN.paper2)
        view.document = document
        view.maxScaleFactor = 4
        view.minScaleFactor = view.scaleFactorForSizeToFit
        return view
    }

    func updateUIView(_ view: PDFView, context: Context) {
        if view.document !== document {
            view.document = document
            view.minScaleFactor = view.scaleFactorForSizeToFit
        }
    }
}
