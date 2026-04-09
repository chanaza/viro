import { Stagehand } from "@browserbasehq/stagehand";
import { VertexGoogleClient } from "./vertexClient.js";
export class BrowserManager {
    model;
    project;
    location;
    stagehand = null;
    page = null;
    constructor(model, project, location) {
        this.model = model;
        this.project = project;
        this.location = location;
    }
    async init() {
        if (this.stagehand)
            return;
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
    get stagehandInstance() {
        if (!this.stagehand)
            throw new Error("Browser not initialized. Call init() first.");
        return this.stagehand;
    }
    async close() {
        if (this.stagehand)
            await this.stagehand.close();
    }
}
