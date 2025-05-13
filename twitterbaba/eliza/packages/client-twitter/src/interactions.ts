import { SearchMode, type Tweet } from "agent-twitter-client";
import {
    composeContext,
    generateMessageResponse,
    generateShouldRespond,
    messageCompletionFooter,
    shouldRespondFooter,
    type Content,
    type HandlerCallback,
    type IAgentRuntime,
    type Memory,
    ModelClass,
    type State,
    stringToUuid,
    elizaLogger,
    getEmbeddingZeroVector,
    type IImageDescriptionService,
    ServiceType
} from "@elizaos/core";
import type { ClientBase } from "./base";
import { sendTweet, wait } from "./utils.ts";
import { initializeApp } from "firebase/app";
import {
    getFirestore,
    getDocs,
    collection,
    query,
    orderBy,
    limit,
    where,
    Timestamp
} from "firebase/firestore/lite";

const firebaseConfig = {
    apiKey: "AIzaSyCcaMz614aGQgt1kQNpHa3fBKSVIWMt2E8",
    authDomain: "babavanga-fa3cc.firebaseapp.com",
    projectId: "babavanga-fa3cc",
    storageBucket: "babavanga-fa3cc.firebasestorage.app",
    messagingSenderId: "455641823708",
    appId: "1:455641823708:web:925dfc22b51224b228b719",
    measurementId: "G-TZ5166LQGX"
};

export const twitterMessageHandlerTemplate =
    `
# Areas of Expertise
{{knowledge}}

# About {{agentName}} (@{{twitterUserName}}):
{{bio}}
{{lore}}
{{topics}}

{{providers}}

{{characterPostExamples}}

{{postDirections}}

Recent interactions between {{agentName}} and other users:
{{recentPostInteractions}}

{{recentPosts}}

# TASK: Generate a post/reply in the voice, style and perspective of {{agentName}} (@{{twitterUserName}}) while using the thread of tweets as additional context:

Current Post:
{{currentPost}}
Here is the descriptions of images in the Current post.
{{imageDescriptions}}

Thread of Tweets You Are Replying To:
{{formattedConversation}}

# Market Data Context (use if relevant):
{{marketData}}

# IMPORTANT PREDICTION RESPONSE GUIDELINES:
If the user is asking about a specific prediction or why you made a specific bet:
1. Use a direct, professional tone - AVOID any mystical language
2. If the prediction appears to be from a database, refer to the data in the news_analysis field
3. Give concrete, data-driven reasons for your prediction decision
4. Your response should be factual and educational, not mysterious or vague
5. Use the first person and be conversational but precise

# INSTRUCTIONS: Generate a post in the voice, style and perspective of {{agentName}} (@{{twitterUserName}}). You MUST include an action if the current post text includes a prompt that is similar to one of the available actions mentioned here:
{{actionNames}}
{{actions}}

Here is the current post text again. Remember to include an action if the current post text includes a prompt that asks for one of the available actions mentioned above (does not need to be exact)
{{currentPost}}
Here is the descriptions of images in the Current post.
{{imageDescriptions}}
` + messageCompletionFooter;

export const twitterShouldRespondTemplate = (targetUsersStr: string) =>
    `# INSTRUCTIONS: Determine if {{agentName}} (@{{twitterUserName}}) should respond to the message and participate in the conversation. Do not comment. Just respond with "true" or "false".

Response options are RESPOND, IGNORE and STOP.

PRIORITY RULE: ALWAYS RESPOND to these users regardless of topic or message content: ${targetUsersStr}. Topic relevance should be ignored for these users.

For other users:
- {{agentName}} should RESPOND to messages directed at them
- {{agentName}} should RESPOND to conversations relevant to their background
- {{agentName}} should RESPOND to market prediction questions
- {{agentName}} should ESPECIALLY RESPOND to any question about "why" you made a prediction/bet
- {{agentName}} should RESPOND if a user is clearly replying to your tweet with a question
- {{agentName}} should IGNORE irrelevant messages
- {{agentName}} should IGNORE very short messages unless directly addressed
- {{agentName}} should STOP if asked to stop
- {{agentName}} should STOP if conversation is concluded
- {{agentName}} is in a room with other users and wants to be conversational, but not annoying.

IMPORTANT:
- If someone asks "why" about a prediction or bet, ALWAYS RESPOND with an explanation.
- Respond to questions about your predictions or market analyses.
- {{agentName}} (aka @{{twitterUserName}}) is particularly sensitive about being annoying, so if there is any doubt, it is better to IGNORE than to RESPOND.
- For users not in the priority list, {{agentName}} (@{{twitterUserName}}) should err on the side of IGNORE rather than RESPOND if in doubt.

Recent Posts:
{{recentPosts}}

Current Post:
{{currentPost}}

Thread of Tweets You Are Replying To:
{{formattedConversation}}

# INSTRUCTIONS: Respond with [RESPOND] if {{agentName}} should respond, or [IGNORE] if {{agentName}} should not respond to the last message and [STOP] if {{agentName}} should stop participating in the conversation.
` + shouldRespondFooter;

export class TwitterInteractionClient {
    client: ClientBase;
    runtime: IAgentRuntime;
    private isDryRun: boolean;
    private app;
    private db;
    
    constructor(client: ClientBase, runtime: IAgentRuntime) {
        this.client = client;
        this.runtime = runtime;
        this.isDryRun = this.client.twitterConfig.TWITTER_DRY_RUN;
        
        try {
            this.app = initializeApp(firebaseConfig);
            this.db = getFirestore(this.app);
            elizaLogger.log("Firebase initialized for Twitter interactions");
        } catch (error) {
            elizaLogger.error("Error initializing Firebase for interactions:", error);
        }
    }

    async start() {
        const handleTwitterInteractionsLoop = () => {
            this.handleTwitterInteractions();
            setTimeout(
                handleTwitterInteractionsLoop,
                this.client.twitterConfig.TWITTER_POLL_INTERVAL * 1000
            );
        };
        handleTwitterInteractionsLoop();
    }

    async handleTwitterInteractions() {
        elizaLogger.log("Checking Twitter interactions");

        const twitterUsername = this.client.profile.username;
        try {
            const mentionCandidates = (
                await this.client.fetchSearchTweets(
                    `@${twitterUsername}`,
                    20,
                    SearchMode.Latest
                )
            ).tweets;

            elizaLogger.log(
                "Completed checking mentioned tweets:",
                mentionCandidates.length
            );
            let uniqueTweetCandidates = [...mentionCandidates];
            if (this.client.twitterConfig.TWITTER_TARGET_USERS.length) {
                const TARGET_USERS =
                    this.client.twitterConfig.TWITTER_TARGET_USERS;

                elizaLogger.log("Processing target users:", TARGET_USERS);

                if (TARGET_USERS.length > 0) {
                    const tweetsByUser = new Map<string, Tweet[]>();

                    for (const username of TARGET_USERS) {
                        try {
                            const userTweets = (
                                await this.client.twitterClient.fetchSearchTweets(
                                    `from:${username}`,
                                    3,
                                    SearchMode.Latest
                                )
                            ).tweets;

                            const validTweets = userTweets.filter((tweet) => {
                                const isUnprocessed =
                                    !this.client.lastCheckedTweetId ||
                                    Number.parseInt(tweet.id) >
                                        this.client.lastCheckedTweetId;
                                const isRecent =
                                    Date.now() - tweet.timestamp * 1000 <
                                    2 * 60 * 60 * 1000;

                                elizaLogger.log(`Tweet ${tweet.id} checks:`, {
                                    isUnprocessed,
                                    isRecent,
                                    isReply: tweet.isReply,
                                    isRetweet: tweet.isRetweet,
                                });

                                return (
                                    isUnprocessed &&
                                    !tweet.isReply &&
                                    !tweet.isRetweet &&
                                    isRecent
                                );
                            });

                            if (validTweets.length > 0) {
                                tweetsByUser.set(username, validTweets);
                                elizaLogger.log(
                                    `Found ${validTweets.length} valid tweets from ${username}`
                                );
                            }
                        } catch (error) {
                            elizaLogger.error(
                                `Error fetching tweets for ${username}:`,
                                error
                            );
                            continue;
                        }
                    }

                    const selectedTweets: Tweet[] = [];
                    tweetsByUser.forEach((tweets, username) => {
                        if (tweets.length > 0) {
                            const randomTweet =
                                tweets[
                                    Math.floor(Math.random() * tweets.length)
                                ];
                            selectedTweets.push(randomTweet);
                            elizaLogger.log(
                                `Selected tweet from ${username}: ${randomTweet.text?.substring(0, 100)}`
                            );
                        }
                    });

                    uniqueTweetCandidates = [
                        ...mentionCandidates,
                        ...selectedTweets,
                    ];
                }
            } else {
                elizaLogger.log(
                    "No target users configured, processing only mentions"
                );
            }

            uniqueTweetCandidates
                .sort((a, b) => a.id.localeCompare(b.id))
                .filter((tweet) => tweet.userId !== this.client.profile.id);

            for (const tweet of uniqueTweetCandidates) {
                if (
                    !this.client.lastCheckedTweetId ||
                    BigInt(tweet.id) > this.client.lastCheckedTweetId
                ) {
                    const tweetId = stringToUuid(
                        tweet.id + "-" + this.runtime.agentId
                    );

                    const existingResponse =
                        await this.runtime.messageManager.getMemoryById(
                            tweetId
                        );

                    if (existingResponse) {
                        elizaLogger.log(
                            `Already responded to tweet ${tweet.id}, skipping`
                        );
                        continue;
                    }
                    elizaLogger.log("New Tweet found", tweet.permanentUrl);

                    const roomId = stringToUuid(
                        tweet.conversationId + "-" + this.runtime.agentId
                    );

                    const userIdUUID =
                        tweet.userId === this.client.profile.id
                            ? this.runtime.agentId
                            : stringToUuid(tweet.userId!);

                    await this.runtime.ensureConnection(
                        userIdUUID,
                        roomId,
                        tweet.username,
                        tweet.name,
                        "twitter"
                    );

                    const thread = await this.buildConversationThread(tweet);

                    const message = {
                        content: { 
                            text: tweet.text,
                            imageUrls: tweet.photos?.map(photo => photo.url) || []
                        },
                        agentId: this.runtime.agentId,
                        userId: userIdUUID,
                        roomId,
                    };

                    await this.handleTweet({
                        tweet,
                        message,
                        thread,
                    });

                    this.client.lastCheckedTweetId = BigInt(tweet.id);
                }
            }

            await this.client.cacheLatestCheckedTweetId();

            elizaLogger.log("Finished checking Twitter interactions");
        } catch (error) {
            elizaLogger.error("Error handling Twitter interactions:", error);
        }
    }

    private async getRecentMarketData(): Promise<string> {
        try {
            elizaLogger.log("Fetching recent market data from Firebase...");
            
            const predictionsRef = collection(this.db, "predictions");
            const q = query(
                predictionsRef,
                where("status", "==", "active"),
                orderBy("timestamp", "desc"),
                limit(3)
            );

            const querySnapshot = await getDocs(q);
            
            if (querySnapshot.empty) {
                elizaLogger.log("No predictions found in database");
                return "No active market predictions available.";
            }
            
            let marketData = "Recent Market Predictions:\n";
            
            for (const doc of querySnapshot.docs) {
                const prediction = doc.data();
                
                marketData += `- Question: ${prediction.question}\n`;
                marketData += `  Position: ${prediction.prediction} at $${prediction.entry_price}\n`;
                
                if (prediction.confidence) {
                    marketData += `  Confidence: ${(prediction.confidence * 100).toFixed(0)}%\n`;
                }
                
                if (prediction.prediction_text || prediction.reasoning) {
                    marketData += `  Reasoning: ${prediction.prediction_text || prediction.reasoning}\n`;
                }
                
                marketData += `  Timestamp: ${new Date(prediction.timestamp?.toDate() || Date.now()).toLocaleString()}\n\n`;
            }
            
            elizaLogger.log("Successfully fetched market data from Firebase");
            return marketData;
        } catch (error) {
            elizaLogger.error("Error fetching market data from Firebase:", error);
            return "Error fetching market data.";
        }
    }

    private isMarketRelatedTweet(tweetText: string): boolean {
        const marketKeywords = [
            'market', 'prediction', 'trade', 'crypto', 'bitcoin', 'eth', 'price',
            'invest', 'trading', 'polymarket', 'bet', 'odds', 'forecast', 
            'probability', 'token', 'coin', 'currency', 'defi', 'stock'
        ];
        
        const lowercaseText = tweetText.toLowerCase();
        
        return marketKeywords.some(keyword => lowercaseText.includes(keyword));
    }

    private async handleTweet({
        tweet,
        message,
        thread,
    }: {
        tweet: Tweet;
        message: Memory;
        thread: Tweet[];
    }) {
        try {
            // Format tweets for context
            const formatTweet = (tweet: Tweet) => {
                return {
                    id: tweet.id,
                    username: tweet.username,
                    text: tweet.text,
                    timestamp: tweet.timestamp,
                };
            };

            const formattedThread = thread.map(formatTweet);
            const formattedConversation = formattedThread
                .map(
                    (t) =>
                        `@${t.username} (${new Date(
                            t.timestamp * 1000
                        ).toLocaleString()}): ${t.text}`
                )
                .join("\n\n");

            // Generate image descriptions if present
            const imageDescriptions = [];
            if (tweet.photos?.length > 0) {
                elizaLogger.log("Processing images in tweet for context");
                for (const photo of tweet.photos) {
                    try {
                        const description = await this.runtime
                            .getService<IImageDescriptionService>(
                                ServiceType.IMAGE_DESCRIPTION
                            )
                            .describeImage(photo.url);
                        imageDescriptions.push(description);
                    } catch (error) {
                        elizaLogger.error(
                            "Error generating image description:",
                            error
                        );
                    }
                }
            }

            // Check if the message is market-related
            const isMarketRelated = this.isMarketRelatedTweet(tweet.text);
            
            // Get market data if relevant
            const marketData = isMarketRelated
                ? await this.getRecentMarketData()
                : "";
                
            // Detectar si está preguntando sobre una predicción o apuesta
            const isAskingAboutPrediction = 
                (tweet.text.toLowerCase().includes("why") && 
                (tweet.text.toLowerCase().includes("bet") || 
                 tweet.text.toLowerCase().includes("predict") ||
                 tweet.text.toLowerCase().includes("think") ||
                 tweet.text.toLowerCase().includes("decision"))) ||
                (tweet.text.toLowerCase().includes("why did you") || 
                 tweet.text.toLowerCase().includes("why are you") || 
                 tweet.text.toLowerCase().includes("why bet") || 
                 tweet.text.toLowerCase().includes("reason"));
            
            // Check if we should respond
            let shouldRespond = false;
            
            // Setup targeted username list
            const targetUsers = this.client.twitterConfig.TWITTER_TARGET_USERS || [];
            const targetUsersString = targetUsers.length > 0 ? 
                targetUsers.map(u => `@${u}`).join(", ") : 
                "None";
            
            try {
                const shouldRespondTemplate =
                    this.runtime.character.templates?.twitterShouldRespondTemplate ||
                    twitterShouldRespondTemplate(targetUsersString);
                
                const shouldRespondState = await this.runtime.composeState(
                    message,
                    {
                        twitterUserName: this.client.profile.username,
                        currentPost: `From @${tweet.username}: ${tweet.text}`,
                        formattedConversation,
                    }
                );
                
                const shouldRespondContext = composeContext({
                    state: shouldRespondState,
                    template: shouldRespondTemplate,
                });
                
                const shouldRespondResult = await generateShouldRespond({
                    runtime: this.runtime,
                    context: shouldRespondContext,
                    modelClass: ModelClass.SMALL,
                });
                
                elizaLogger.log(`Should respond result: ${shouldRespondResult}`);
                
                if (shouldRespondResult === "RESPOND") {
                    shouldRespond = true;
                } else if (shouldRespondResult === "STOP") {
                    elizaLogger.log("Message indicates conversation should stop");
                    return;
                }
            } catch (error) {
                elizaLogger.error("Error determining if should respond:", error);
            }

            // Alway respond to direct mentions, regardless of "shouldRespond" value
            const isDirect = tweet.text.toLowerCase().includes(
                `@${this.client.profile.username.toLowerCase()}`
            );
            
            // Automatically respond to target users
            const isTargetUser = targetUsers.some(
                (username) => username.toLowerCase() === tweet.username.toLowerCase()
            );
            
            // Detectar si es una respuesta directa a un tweet del bot
            const isDirectReplyToBot = thread.some(t => 
                t.id === tweet.inReplyToStatusId && 
                t.username.toLowerCase() === this.client.profile.username.toLowerCase()
            );
            
            // Responder si es una mención directa, usuario objetivo, respuesta directa al bot, pregunta sobre predicción, o shouldRespond es true
            if (isDirect || isTargetUser || isDirectReplyToBot || (isAskingAboutPrediction && isDirectReplyToBot) || shouldRespond) {
                elizaLogger.log(
                    `${
                        isDirect
                            ? "Direct mention"
                            : isTargetUser
                            ? "Target user"
                            : isDirectReplyToBot
                            ? "Direct reply to bot"
                            : isAskingAboutPrediction && isDirectReplyToBot
                            ? "Question about prediction"
                            : "Content relevance"
                    } triggered response to tweet from @${tweet.username}`
                );
                
                // Check if this is a question about a previous prediction
                let predictionData = "";
                // Si pregunta sobre una predicción, intentar encontrar datos relevantes
                if (isAskingAboutPrediction && this.db) {
                    try {
                        elizaLogger.log("Detected question about prediction, searching for data...");
                        // ... el resto del código para buscar predicciones ...
                        // Ya está implementado correctamente
                    } catch (error) {
                        elizaLogger.error("Error searching for prediction data:", error);
                    }
                }
                
                // Create rich tweet state with all context including prediction data
                const tweetState = await this.runtime.composeState(
                    message,
                    {
                        twitterUserName: this.client.profile.username,
                        currentPost: `From @${tweet.username}: ${tweet.text}`,
                        formattedConversation,
                        marketData,
                        imageDescriptions:
                            imageDescriptions.length > 0
                                ? `\nImages in Tweet:\n${imageDescriptions
                                      .map((desc, i) => `Image ${i + 1}: ${desc}`)
                                      .join("\n")}`
                                : "",
                        predictionData, // Add the prediction data to the context
                    }
                );
                
                // Generate and clean the response
                const context = composeContext({
                    state: tweetState,
                    template:
                        this.runtime.character.templates
                            ?.twitterMessageHandlerTemplate ||
                        twitterMessageHandlerTemplate,
                });

                const response = await generateMessageResponse({
                    runtime: this.runtime,
                    context,
                    modelClass: ModelClass.SMALL,
                });
                
                // Use callback to handle response
                const removeQuotes = (str: string) =>
                    str.replace(/^['"](.*)['"]$/, "$1");
                
                if (response) {
                    // Log the type of response we got
                    elizaLogger.log(`Got response type: ${typeof response}`);
                    
                    // Extract the text content regardless of format
                    let textContent = "";
                    
                    if (typeof response === "string") {
                        textContent = response;
                    } else if (response && typeof response === "object") {
                        // Intentar acceder a propiedades comunes
                        const resp = response as any;
                        if (resp.text) {
                            textContent = resp.text;
                        } else if (resp.content) {
                            textContent = resp.content;
                        } else if (resp.message) {
                            textContent = resp.message;
                        } else {
                            try {
                                textContent = JSON.stringify(resp);
                            } catch (e) {
                                elizaLogger.error("Could not convert response to string");
                                return;
                            }
                        }
                    } else {
                        elizaLogger.error("Unexpected response format:", typeof response);
                        return;
                    }
                    
                    try {
                        const processed = removeQuotes(textContent);
                        
                        if (!processed || processed.trim().length === 0) {
                            elizaLogger.warn("Empty response, not replying");
                            return;
                        }
                        
                        elizaLogger.log(`Sending tweet response: ${processed.substring(0, 50)}...`);
                        
                        if (this.isDryRun) {
                            elizaLogger.info(`DRY RUN: Would send tweet: ${processed}`);
                            elizaLogger.info(`DRY RUN: Tweet would be in response to: ${tweet.id}`);
                            return;
                        }
                        
                        const result = await this.sendTweetReply(processed, tweet.id);
                        
                        if (result) {
                            elizaLogger.success("Tweet sent successfully");
                        } else {
                            elizaLogger.error("Tweet sending failed");
                        }
                    } catch (error) {
                        elizaLogger.error("Error processing response:", error);
                    }
                }
            } else {
                elizaLogger.log(
                    `Decided not to respond to tweet from @${tweet.username}`
                );
            }
        } catch (error) {
            elizaLogger.error("Error handling tweet:", error);
        }
    }

    /**
     * Construye un hilo de conversación para un tweet dado
     */
    async buildConversationThread(
        tweet: Tweet,
        maxReplies = 10
    ): Promise<Tweet[]> {
        const thread: Tweet[] = [];
        const visited: Set<string> = new Set();
        const client = this.client;
        const runtime = this.runtime;

        async function processThread(currentTweet: Tweet, depth = 0) {
            elizaLogger.log("Processing tweet:", {
                id: currentTweet.id,
                inReplyToStatusId: currentTweet.inReplyToStatusId,
                depth: depth,
            });

            if (!currentTweet) {
                elizaLogger.log("No current tweet found for thread building");
                return;
            }

            if (depth >= maxReplies) {
                elizaLogger.log("Reached maximum reply depth", depth);
                return;
            }

            // Handle memory storage
            const memory = await runtime.messageManager.getMemoryById(
                stringToUuid(currentTweet.id + "-" + runtime.agentId)
            );
            if (!memory) {
                const roomId = stringToUuid(
                    currentTweet.conversationId + "-" + runtime.agentId
                );
                const userId = stringToUuid(currentTweet.userId);

                await runtime.ensureConnection(
                    userId,
                    roomId,
                    currentTweet.username,
                    currentTweet.name,
                    "twitter"
                );

                runtime.messageManager.createMemory({
                    id: stringToUuid(
                        currentTweet.id + "-" + runtime.agentId
                    ),
                    agentId: runtime.agentId,
                    content: {
                        text: currentTweet.text,
                        source: "twitter",
                        url: currentTweet.permanentUrl,
                        imageUrls: currentTweet.photos?.map(photo => photo.url) || [],
                        inReplyTo: currentTweet.inReplyToStatusId
                            ? stringToUuid(
                                  currentTweet.inReplyToStatusId +
                                      "-" +
                                      runtime.agentId
                              )
                            : undefined,
                    },
                    createdAt: currentTweet.timestamp * 1000,
                    roomId,
                    userId:
                        currentTweet.userId === client.profile.id
                            ? runtime.agentId
                            : stringToUuid(currentTweet.userId),
                    embedding: getEmbeddingZeroVector(),
                });
            }

            if (visited.has(currentTweet.id)) {
                elizaLogger.log("Already visited tweet:", currentTweet.id);
                return;
            }

            visited.add(currentTweet.id);
            thread.unshift(currentTweet);

            if (currentTweet.inReplyToStatusId) {
                elizaLogger.log(
                    "Fetching parent tweet:",
                    currentTweet.inReplyToStatusId
                );
                try {
                    const parentTweet = await client.twitterClient.getTweet(
                        currentTweet.inReplyToStatusId
                    );

                    if (parentTweet) {
                        elizaLogger.log("Found parent tweet:", {
                            id: parentTweet.id,
                            text: parentTweet.text?.slice(0, 50),
                        });
                        await processThread(parentTweet, depth + 1);
                    } else {
                        elizaLogger.log(
                            "No parent tweet found for:",
                            currentTweet.inReplyToStatusId
                        );
                    }
                } catch (error) {
                    elizaLogger.log("Error fetching parent tweet:", {
                        tweetId: currentTweet.inReplyToStatusId,
                        error,
                    });
                }
            } else {
                elizaLogger.log(
                    "Reached end of reply chain at:",
                    currentTweet.id
                );
            }
        }

        // Iniciamos el procesamiento recursivo
        await processThread(tweet, 0);

        return thread;
    }

    /**
     * Envía una respuesta a un tweet
     */
    private async sendTweetReply(content: string, inReplyToId?: string): Promise<any> {
        try {
            if (!this.client.twitterClient) {
                elizaLogger.error("Twitter client is not initialized");
                return null;
            }
            
            // Asegurarse de que el contenido sea una cadena válida
            if (!content || typeof content !== 'string') {
                elizaLogger.error("Invalid content for tweet reply:", typeof content);
                return null;
            }
            
            // Eliminar comillas iniciales y finales si existen
            const processedContent = content.replace(/^['"](.*)['"]$/, "$1").trim();
            
            if (!processedContent || processedContent.trim().length === 0) {
                elizaLogger.error("Empty content after processing, not sending tweet");
                return null;
            }
            
            elizaLogger.log(`Sending tweet reply: ${processedContent.substring(0, 50)}...`);
            
            // If we're in dry run mode, just log and return
            if (this.isDryRun) {
                elizaLogger.info(`DRY RUN: Would send tweet: ${processedContent}`);
                if (inReplyToId) {
                    elizaLogger.info(`DRY RUN: Tweet would be in response to: ${inReplyToId}`);
                }
                return true;
            }
            
            try {
                let result = null;
                
                // Si hay requestQueue, utilizarlo para evitar límites de tasa
                if (this.client.requestQueue) {
                    elizaLogger.log("Using request queue for tweet posting");
                    result = await this.client.requestQueue.add(async () => {
                        const tweetResult = await this.client.twitterClient.sendTweet(processedContent, inReplyToId);
                        return tweetResult;
                    });
                } else {
                    // Llamada directa sin queue
                    elizaLogger.log("Using direct API call for tweet posting");
                    result = await this.client.twitterClient.sendTweet(processedContent, inReplyToId);
                }
                
                if (result) {
                    elizaLogger.success(`Tweet reply sent successfully with ID: ${result.id || 'unknown'}`);
                    return result;
                } else {
                    elizaLogger.error("Failed to send tweet reply - no result returned");
                    return null;
                }
            } catch (twitterError) {
                elizaLogger.error("Twitter API error sending reply:", twitterError);
                
                // Reintento una vez si hay un error transitorio
                if (typeof twitterError === 'object' && 
                    twitterError !== null && 
                    'status' in twitterError && 
                    (twitterError.status === 429 || twitterError.status === 503)) {
                    
                    elizaLogger.log("Rate limit or server error detected, retrying after delay...");
                    await wait(5000); // Esperar 5 segundos antes de reintentar
                    
                    try {
                        const retryResult = await this.client.twitterClient.sendTweet(processedContent, inReplyToId);
                        if (retryResult) {
                            elizaLogger.success("Tweet reply sent successfully on retry");
                            return retryResult;
                        }
                    } catch (retryError) {
                        elizaLogger.error("Failed on retry attempt:", retryError);
                    }
                }
                
                return null;
            }
        } catch (error) {
            elizaLogger.error("Error sending tweet reply:", error);
            return null;
        }
    }
}