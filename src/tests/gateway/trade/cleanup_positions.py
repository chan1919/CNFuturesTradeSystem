"""Close leftover positions using the shared integration harness."""
from src.tests.gateway.trade._integration_support import GatewayIntegrationHarness


def main():
    harness = GatewayIntegrationHarness()
    try:
        harness.connect_td()
        harness.cleanup_positions()
        print("Cleanup completed.")
    finally:
        harness.close()


if __name__ == "__main__":
    main()
