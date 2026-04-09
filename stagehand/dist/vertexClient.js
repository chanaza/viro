/**
 * Custom Stagehand LLMClient that uses @google/genai with Vertex AI (ADC auth).
 * Based on Stagehand's GoogleClient but uses vertexai:true instead of apiKey.
 */
import { GoogleGenAI, HarmCategory, HarmBlockThreshold, Type, } from "@google/genai";
import { LLMClient, } from "@browserbasehq/stagehand";
import { toGeminiSchema, validateZodSchema } from "@browserbasehq/stagehand";
const roleMap = {
    user: "user",
    assistant: "model",
    system: "user",
};
const safetySettings = [
    { category: HarmCategory.HARM_CATEGORY_HARASSMENT, threshold: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE },
    { category: HarmCategory.HARM_CATEGORY_HATE_SPEECH, threshold: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE },
    { category: HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT, threshold: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE },
    { category: HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT, threshold: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE },
];
export class VertexGoogleClient extends LLMClient {
    type = "google";
    hasVision = true;
    clientOptions = {};
    client;
    constructor({ modelName, project, location, }) {
        super(modelName);
        this.modelName = modelName;
        this.client = new GoogleGenAI({ vertexai: true, project, location });
    }
    formatMessages(messages, image) {
        const contents = [];
        let systemInstruction = null;
        messages.forEach((msg, index) => {
            const role = roleMap[msg.role];
            if (!role)
                return;
            if (msg.role === "system") {
                if (typeof msg.content === "string") {
                    systemInstruction = (systemInstruction ? systemInstruction + "\n\n" : "") + msg.content;
                }
                return;
            }
            const parts = [];
            if (Array.isArray(msg.content)) {
                msg.content.forEach((part) => {
                    if (part.type === "text")
                        parts.push({ text: part.text });
                    else if (part.type === "image_url" && part.image_url?.url) {
                        const base64Data = part.image_url.url.split(",")[1];
                        const mimeMatch = part.image_url.url.match(/^data:(image\/\w+);base64,/);
                        if (base64Data && mimeMatch)
                            parts.push({ inlineData: { mimeType: mimeMatch[1], data: base64Data } });
                    }
                });
            }
            else if (typeof msg.content === "string") {
                parts.push({ text: msg.content });
            }
            if (image && index === messages.length - 1 && msg.role === "user") {
                parts.push({ text: image.description || "Screenshot of current page state." });
                parts.push({ inlineData: { mimeType: "image/jpeg", data: image.buffer.toString("base64") } });
            }
            if (systemInstruction && contents.length === 0 && role === "user") {
                const first = parts.find((p) => "text" in p);
                if (first)
                    first.text = `${systemInstruction}\n\n${first.text}`;
                else
                    parts.unshift({ text: systemInstruction });
                systemInstruction = null;
            }
            if (parts.length > 0)
                contents.push({ role, parts });
        });
        if (systemInstruction)
            contents.unshift({ role: "user", parts: [{ text: systemInstruction }] });
        return contents;
    }
    formatTools(tools) {
        if (!tools?.length)
            return undefined;
        return [{
                functionDeclarations: tools.map((tool) => ({
                    name: tool.name,
                    description: tool.description,
                    parameters: tool.parameters ? {
                        type: Type.OBJECT,
                        properties: tool.parameters.properties,
                        required: tool.parameters.required,
                    } : undefined,
                })),
            }];
    }
    async createChatCompletion({ options, logger, retries = 3, }) {
        const { image, requestId, response_model, tools, temperature, top_p, maxOutputTokens } = options;
        const contents = this.formatMessages(options.messages, image);
        const formattedTools = this.formatTools(tools);
        const generationConfig = {
            maxOutputTokens,
            temperature,
            topP: top_p,
            responseMimeType: response_model ? "application/json" : undefined,
            responseSchema: response_model ? toGeminiSchema(response_model.schema) : undefined,
        };
        try {
            const result = await this.client.models.generateContent({
                model: this.modelName,
                contents,
                config: { ...generationConfig, safetySettings, tools: formattedTools },
            });
            const toolCalls = result.functionCalls?.map((fc, i) => ({
                id: `tool_call_${requestId}_${i}`,
                type: "function",
                function: { name: fc.name, arguments: JSON.stringify(fc.args) },
            }));
            let content = null;
            try {
                content = result.text ?? null;
            }
            catch { }
            const llmResponse = {
                id: result.candidates?.[0]?.index?.toString() || requestId || "0",
                object: "chat.completion",
                created: Math.floor(Date.now() / 1000),
                model: this.modelName,
                choices: [{ index: 0, message: { role: "assistant", content, tool_calls: toolCalls ?? [] }, finish_reason: result.candidates?.[0]?.finishReason || "stop" }],
                usage: {
                    prompt_tokens: result.usageMetadata?.promptTokenCount || 0,
                    completion_tokens: result.usageMetadata?.candidatesTokenCount || 0,
                    total_tokens: result.usageMetadata?.totalTokenCount || 0,
                },
            };
            if (response_model) {
                let parsedData;
                try {
                    parsedData = JSON.parse(content?.trim().replace(/^```json\n?|\n?```$/g, "") || "{}");
                }
                catch {
                    if (retries > 0)
                        return this.createChatCompletion({ options, logger, retries: retries - 1 });
                    throw new Error("Failed to parse JSON response");
                }
                validateZodSchema(response_model.schema, parsedData);
                return { data: parsedData, usage: llmResponse.usage };
            }
            return llmResponse;
        }
        catch (error) {
            if (retries > 0) {
                await new Promise((r) => setTimeout(r, 1000 * (4 - retries)));
                return this.createChatCompletion({ options, logger, retries: retries - 1 });
            }
            throw error;
        }
    }
}
