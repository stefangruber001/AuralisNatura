import SwiftUI

struct MainTabView: View {
    @EnvironmentObject private var router: TabRouter
    @EnvironmentObject private var session: SessionStore

    var body: some View {
        TabView(selection: $router.tab) {
            tabRoot { HomeView() }
                .tabItem { Label(L10n["tab.home"], systemImage: "house") }
                .tag(TabRouter.Tab.home)

            tabRoot { ProgrammeView() }
                .tabItem { Label(L10n["tab.programmes"], systemImage: "sparkles") }
                .tag(TabRouter.Tab.programmes)

            tabRoot { TerminWebView() }
                .tabItem { Label(L10n["tab.booking"], systemImage: "calendar") }
                .tag(TabRouter.Tab.booking)

            // Journey moved into Profile ("Dokumente" already pushes it) so this
            // slot could carry Impulse — the tab bar holds five. A guest reads the
            // public feed through the same view.
            tabRoot { ImpulseView(guestMode: session.isGuest) }
                .tabItem { Label(L10n["tab.impulse"], systemImage: "book.closed") }
                .tag(TabRouter.Tab.impulse)

            tabRoot { ProfileView() }
                .tabItem { Label(L10n["tab.profile"], systemImage: "person.crop.circle") }
                .tag(TabRouter.Tab.profile)
        }
        .tint(AN.clay)
        .task {
            // A guest starts where there is something to see: the programmes.
            // Home for her is an introduction, not a dashboard.
            if session.isGuest && router.tab == .home {
                router.tab = .programmes
            }
            if !session.isGuest && session.me == nil {
                await session.refreshMe()
            }
        }
    }

    /// Every tab: the BrandBar as a real layout sibling ABOVE the content, so
    /// content can never slide underneath it (a `.safeAreaInset` on the
    /// NavigationStack proved unreliable — the first rows were clipped under the
    /// bar). A plain VStack is deterministic; the paper background is pushed up
    /// into the status-bar strip so it reads as one continuous surface.
    private func tabRoot<Content: View>(@ViewBuilder content: () -> Content) -> some View {
        VStack(spacing: 0) {
            BrandBar()
            NavigationStack {
                content()
                    .toolbar(.hidden, for: .navigationBar)
            }
        }
        .background(AN.paper.ignoresSafeArea())
    }
}
