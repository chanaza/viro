import * as dotenv from "dotenv";
import { ResearchPipeline } from "./pipeline.js";

dotenv.config();

await new ResearchPipeline(process.env.SUBJECT ?? "שופרסל").run();
