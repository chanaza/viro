import { Stagehand } from "@browserbasehq/stagehand";
import { VertexGoogleClient } from "./vertexClient.js";

export class BrowserManager {
  private stagehand: Stagehand | null = null;
  public page: any = null;

  constructor(
    private readonly model: string,
    private readonly project: string,
    private readonly location: string,
  ) {}

  async init(): Promise<void> {
    if (this.stagehand) return;

    this.stagehand = new Stagehand({
      env: "LOCAL",
      llmClient: new VertexGoogleClient({
        modelName: this.model,
        project: this.project,
        location: this.location,
      }),
      verbose: 1,
    });
    await this.stagehand.init();
    this.page = this.stagehand.context.pages()[0];
  }

  get stagehandInstance(): Stagehand {
    if (!this.stagehand) throw new Error("Browser not initialized. Call init() first.");
    return this.stagehand;
  }

  async close(): Promise<void> {
    if (this.stagehand) await this.stagehand.close();
  }
}
