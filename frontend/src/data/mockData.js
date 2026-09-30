/**
 * Local mock data for the AI Research Agent frontend.
 * No backend or API integration — purely static, illustrative data.
 */

export const mockResearchEntries = [
  {
    id: 'research-1',
    title: 'FastAPI Dependency Injection',
    status: 'Completed',
    summary:
      'FastAPI uses dependency injection to provide reusable components and shared resources to route handlers. This pattern promotes clean architecture and testable code.',
    keyFindings: [
      'Depends() declares dependencies at the route level.',
      'Dependencies can have sub-dependencies, forming a dependency tree.',
      'Yield dependencies support resource cleanup after request completion.',
      'Dependency overrides simplify testing by swapping implementations.',
    ],
    sources: ['FastAPI documentation', 'Example research source'],
  },
  {
    id: 'research-2',
    title: 'Redis Architecture',
    status: 'Completed',
    summary:
      'Redis is an in-memory data structure store used as a database, cache, and message broker. Its single-threaded architecture ensures atomicity of individual operations.',
    keyFindings: [
      'Redis stores data in memory for sub-millisecond read/write latency.',
      'Data structures include strings, hashes, lists, sets, and sorted sets.',
      'Persistence is supported through RDB snapshots and AOF logs.',
      'Pub/Sub and Streams enable real-time messaging patterns.',
    ],
    sources: ['Redis official documentation', 'Redis University courses'],
  },
  {
    id: 'research-3',
    title: 'LangGraph Workflows',
    status: 'Completed',
    summary:
      'LangGraph extends LangChain to build stateful, multi-step agent workflows as directed graphs. Nodes represent processing steps and edges define control flow.',
    keyFindings: [
      'StateGraph manages shared state across workflow nodes.',
      'Conditional edges allow dynamic routing based on state.',
      'Checkpointing enables workflow persistence and recovery.',
      'Human-in-the-loop patterns are supported via interrupt nodes.',
    ],
    sources: ['LangGraph documentation', 'LangChain blog posts'],
  },
  {
    id: 'research-4',
    title: 'RAG Pipeline Design',
    status: 'Completed',
    summary:
      'Retrieval-Augmented Generation (RAG) combines document retrieval with language model generation to produce grounded, factual responses from a knowledge base.',
    keyFindings: [
      'Documents are chunked and embedded into a vector store for retrieval.',
      'Similarity search retrieves the most relevant chunks for a query.',
      'Retrieved context is injected into the LLM prompt for generation.',
      'Evaluation metrics include faithfulness, relevance, and answer correctness.',
    ],
    sources: ['LangChain RAG tutorials', 'Chroma documentation'],
  },
];
