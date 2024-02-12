pub mod api;
pub mod rate_limiter;
pub mod signals;
pub mod config;

use salvo::{
    prelude::*,
    rate_limiter::RemoteIpIssuer,
    proxy::Proxy
};

use rate_limiter::{
    MultiSlidingGuard,
    RateLimiter,
    Cache
};
use api::update_metrics;
use config::Config;


#[tokio::main]
async fn main() {
    tracing_subscriber::fmt().init();

    if let Some(config) = Config::load_config() {
        let limiter =
            RateLimiter::new(
                MultiSlidingGuard::new(3),
                Cache::default(),
                RemoteIpIssuer,
            );

        let internal_router =
            Router::with_path("/metrics")
                .goal(update_metrics);

        let proxy_router =
            Router::with_path("/<**rest>")
                .hoop(limiter)
                .goal(
                    Proxy::default_hyper_client(config.upstream().to_string())
                );

        let internal_server =
            Server::new(
                TcpListener::new("0.0.0.0:5800")
                    .bind()
                    .await
            );

        let proxy_server =
            Server::new(
                TcpListener::new("0.0.0.0:5801")
                    .bind()
                    .await
            );

        tokio::spawn(
            signals::listen_shutdown_signal(
                internal_server.handle(),
                proxy_server.handle()
            )
        );

        if let Err(reason) = tokio::try_join!(
            internal_server
                .try_serve(internal_router),
            proxy_server
                .try_serve(proxy_router),
        )
        {
            tracing::error!(
                error = ?reason,
                "{}",
                reason
            );
        }
    } else {
        tracing::error!("Failed to read configuration file")
    }
}
