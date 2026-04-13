import { Container } from "@cloudflare/containers";

export class YibiaoApp extends Container {
  defaultPort = 8000;
  requiredPorts = [8000];
  sleepAfter = "2h";
  enableInternet = true;
  pingEndpoint = "/health";
  envVars = {
    ENABLE_SEARCH_ROUTER: "false",
  };
}

interface Env {
  APP: DurableObjectNamespace<YibiaoApp>;
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const container = env.APP.getByName("singleton");
    await container.startAndWaitForPorts();
    return container.fetch(request);
  },
};
