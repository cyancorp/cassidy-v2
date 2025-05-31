export interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp?: Date;
}

// Add other types as needed, e.g., for structured content
// export interface StructuredContent { ... } 

export interface TemplateSectionDetail {
  description: string;
  aliases: string[];
}

export interface UserTemplate {
  sections: { [key: string]: TemplateSectionDetail };
  last_updated?: string; // Or Date, if parsed
} 