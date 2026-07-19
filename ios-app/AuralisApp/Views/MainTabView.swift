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

            tabRoot { JourneyView() }
                .tabItem { Label(L10n["tab.journey"], systemImage: "leaf") }
                .tag(TabRouter.Tab.journey)

            tabRoot { ProfileView() }
                .tabItem { Label(L10n["tab.profile"], systemImage: "person.crop.circle") }
                .tag(TabRouter.Tab.profile)
        }
        .tint(AN.clay)
        .task {
            if session.me == nil {
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
