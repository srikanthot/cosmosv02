### DATA SOURCE
{
  "name": "pseg-techm-blob-ds-vnext",
  "type": "azureblob",
  "credentials": {
    "connectionString": "<STORAGE_CONN_STR>"
  },
  "container": {
    "name": "containerpsegtmandev01",
    "query": ""
  },
  "dataChangeDetectionPolicy": {
    "@odata.type": "#Microsoft.Azure.Search.HighWaterMarkChangeDetectionPolicy",
    "highWaterMarkColumnName": "metadata_storage_last_modified"
  },
  "dataDeletionDetectionPolicy": {
    "@odata.type": "#Microsoft.Azure.Search.NativeBlobSoftDeleteDeletionDetectionPolicy"
  }
}

### Index

{
  "name": "rag-psegtechm-index-vnext",
  "fields": [
    {
      "name": "content_id",
      "type": "Edm.String",
      "key": true,
      "retrievable": true,
      "searchable": true,
      "filterable": true,
      "sortable": true,
      "facetable": false,
      "analyzer": "keyword"
    },
    {
      "name": "text_document_id",
      "type": "Edm.String",
      "searchable": false,
      "filterable": true,
      "retrievable": true,
      "stored": true,
      "sortable": false,
      "facetable": false
    },
    {
      "name": "image_document_id",
      "type": "Edm.String",
      "searchable": false,
      "filterable": true,
      "retrievable": true,
      "stored": true,
      "sortable": false,
      "facetable": false
    },
    {
      "name": "record_type",
      "type": "Edm.String",
      "searchable": false,
      "filterable": true,
      "retrievable": true,
      "sortable": true,
      "facetable": true
    },
    {
      "name": "document_title",
      "type": "Edm.String",
      "searchable": true,
      "filterable": true,
      "retrievable": true,
      "sortable": true,
      "facetable": false
    },
    {
      "name": "source_file",
      "type": "Edm.String",
      "searchable": true,
      "filterable": true,
      "retrievable": true,
      "sortable": true,
      "facetable": true
    },
    {
      "name": "source_url",
      "type": "Edm.String",
      "searchable": false,
      "filterable": false,
      "retrievable": true,
      "sortable": false,
      "facetable": false
    },
    {
      "name": "content_text",
      "type": "Edm.String",
      "searchable": true,
      "retrievable": true,
      "stored": true,
      "sortable": false,
      "facetable": false
    },
    {
      "name": "content_embedding",
      "type": "Collection(Edm.Single)",
      "dimensions": 1536,
      "searchable": true,
      "retrievable": false,
      "stored": false,
      "filterable": false,
      "sortable": false,
      "facetable": false,
      "vectorSearchProfile": "pseg-hnsw-profile"
    },
    {
      "name": "content_path",
      "type": "Edm.String",
      "searchable": false,
      "filterable": false,
      "retrievable": true,
      "sortable": false,
      "facetable": false
    },
    {
      "name": "page_number",
      "type": "Edm.Int32",
      "searchable": false,
      "filterable": true,
      "retrievable": true,
      "sortable": true,
      "facetable": true
    },
    {
      "name": "layout_ordinal",
      "type": "Edm.Int32",
      "searchable": false,
      "filterable": true,
      "retrievable": true,
      "sortable": true,
      "facetable": false
    },
    {
      "name": "bounding_polygons",
      "type": "Edm.String",
      "searchable": false,
      "filterable": false,
      "retrievable": true,
      "sortable": false,
      "facetable": false
    }
  ],
  "similarity": {
    "@odata.type": "#Microsoft.Azure.Search.BM25Similarity"
  },
  "semantic": {
    "defaultConfiguration": "manual-semantic-config",
    "configurations": [
      {
        "name": "manual-semantic-config",
        "prioritizedFields": {
          "titleField": {
            "fieldName": "document_title"
          },
          "prioritizedContentFields": [
            {
              "fieldName": "content_text"
            }
          ],
          "prioritizedKeywordsFields": [
            {
              "fieldName": "source_file"
            }
          ]
        }
      }
    ]
  },
  "vectorSearch": {
    "algorithms": [
      {
        "name": "pseg-hnsw-algo",
        "kind": "hnsw",
        "hnswParameters": {
          "m": 8,
          "efConstruction": 800,
          "efSearch": 800,
          "metric": "cosine"
        }
      }
    ],
    "profiles": [
      {
        "name": "pseg-hnsw-profile",
        "algorithm": "pseg-hnsw-algo"
      }
    ],
    "vectorizers": [],
    "compressions": []
  }
}

### SKILLSET

{
  "name": "pseg-techm-skillset-vnext",
  "description": "High-precision multimodal skillset for technical manuals using Document Intelligence layout, OCR, GPT-4.1 image verbalization, and ada-002 embeddings",
  "skills": [
    {
      "@odata.type": "#Microsoft.Skills.Util.DocumentIntelligenceLayoutSkill",
      "name": "document-layout-skill",
      "description": "Document Intelligence layout extraction with text chunks, images, and location metadata",
      "context": "/document",
      "outputMode": "oneToMany",
      "outputFormat": "text",
      "extractionOptions": [
        "images",
        "locationMetadata"
      ],
      "chunkingProperties": {
        "unit": "characters",
        "maximumLength": 2000,
        "overlapLength": 200
      },
      "inputs": [
        {
          "name": "file_data",
          "source": "/document/file_data"
        }
      ],
      "outputs": [
        {
          "name": "text_sections",
          "targetName": "text_sections"
        },
        {
          "name": "normalized_images",
          "targetName": "normalized_images"
        }
      ]
    },
    {
      "@odata.type": "#Microsoft.Skills.Vision.OcrSkill",
      "name": "ocr-skill",
      "description": "OCR over extracted images for labels, warnings, callouts, and scanned text",
      "context": "/document/normalized_images/*",
      "defaultLanguageCode": "en",
      "detectOrientation": true,
      "inputs": [
        {
          "name": "image",
          "source": "/document/normalized_images/*"
        }
      ],
      "outputs": [
        {
          "name": "text",
          "targetName": "ocrText"
        }
      ]
    },
    {
      "@odata.type": "#Microsoft.Skills.Custom.ChatCompletionSkill",
      "name": "genai-image-verbalization-skill",
      "description": "Generate grounded technical descriptions for diagrams, figures, screenshots, schematics, and tables",
      "context": "/document/normalized_images/*",
      "uri": "https://azopenai-pseg-tman-dev01.openai.azure.us/openai/deployments/<GPT41_CHAT_DEPLOYMENT>/chat/completions?api-version=2024-10-21",
      "timeout": "PT1M",
      "apiKey": "<GPT41_API_KEY>",
      "responseFormat": {
        "type": "text"
      },
      "commonModelParameters": {
        "temperature": 0.1,
        "maxTokens": 600
      },
      "inputs": [
        {
          "name": "image",
          "source": "/document/normalized_images/*/data"
        },
        {
          "name": "imageDetail",
          "source": "=high"
        },
        {
          "name": "systemMessage",
          "source": "='You are extracting grounded evidence from technical manual images. Describe only what is visibly present. Focus on equipment names, labels, warnings, switches, valves, transformer names, wire identifiers, table headers, units, part numbers, numbered steps, and safety-critical details. Do not guess.'"
        },
        {
          "name": "userMessage",
          "source": "='Describe this image for search and retrieval. Be concise but precise. Include any visible labels, abbreviations, component names, table-like structure, or procedural clues.'"
        }
      ],
      "outputs": [
        {
          "name": "response",
          "targetName": "verbalizedImage"
        }
      ]
    },
    {
      "@odata.type": "#Microsoft.Skills.Text.MergeSkill",
      "name": "merge-image-evidence-skill",
      "description": "Merge OCR text and image verbalization into one image-searchable field",
      "context": "/document/normalized_images/*",
      "insertPreTag": " ",
      "insertPostTag": " ",
      "inputs": [
        {
          "name": "text",
          "source": "/document/normalized_images/*/verbalizedImage"
        },
        {
          "name": "itemsToInsert",
          "source": "/document/normalized_images/*/ocrText"
        }
      ],
      "outputs": [
        {
          "name": "mergedText",
          "targetName": "imageSearchText"
        }
      ]
    },
    {
      "@odata.type": "#Microsoft.Skills.Text.AzureOpenAIEmbeddingSkill",
      "name": "text-embedding-skill",
      "description": "Embeddings for text chunks",
      "context": "/document/text_sections/*",
      "resourceUri": "https://azopenai-pseg-tman-dev01.openai.azure.us/",
      "apiKey": "<AOAI_API_KEY>",
      "deploymentId": "textembeddingadapsegtm",
      "modelName": "text-embedding-ada-002",
      "dimensions": 1536,
      "inputs": [
        {
          "name": "text",
          "source": "/document/text_sections/*/content"
        }
      ],
      "outputs": [
        {
          "name": "embedding",
          "targetName": "text_vector"
        }
      ]
    },
    {
      "@odata.type": "#Microsoft.Skills.Text.AzureOpenAIEmbeddingSkill",
      "name": "image-text-embedding-skill",
      "description": "Embeddings for verbalized image content",
      "context": "/document/normalized_images/*",
      "resourceUri": "https://azopenai-pseg-tman-dev01.openai.azure.us/",
      "apiKey": "<AOAI_API_KEY>",
      "deploymentId": "textembeddingadapsegtm",
      "modelName": "text-embedding-ada-002",
      "dimensions": 1536,
      "inputs": [
        {
          "name": "text",
          "source": "/document/normalized_images/*/imageSearchText"
        }
      ],
      "outputs": [
        {
          "name": "embedding",
          "targetName": "image_vector"
        }
      ]
    }
  ],
  "cognitiveServices": {
    "@odata.type": "#Microsoft.Azure.Search.CognitiveServicesByKey",
    "key": "<AI_SERVICES_KEY>"
  },
  "indexProjections": {
    "selectors": [
      {
        "targetIndexName": "rag-psegtechm-index-vnext",
        "parentKeyFieldName": "text_document_id",
        "sourceContext": "/document/text_sections/*",
        "mappings": [
          {
            "name": "record_type",
            "source": "='text'"
          },
          {
            "name": "content_embedding",
            "source": "/document/text_sections/*/text_vector"
          },
          {
            "name": "content_text",
            "source": "/document/text_sections/*/content"
          },
          {
            "name": "page_number",
            "source": "/document/text_sections/*/locationMetadata/pageNumber"
          },
          {
            "name": "layout_ordinal",
            "source": "/document/text_sections/*/locationMetadata/ordinalPosition"
          },
          {
            "name": "bounding_polygons",
            "source": "/document/text_sections/*/locationMetadata/boundingPolygons"
          },
          {
            "name": "document_title",
            "source": "/document/metadata_storage_name"
          },
          {
            "name": "source_file",
            "source": "/document/metadata_storage_name"
          },
          {
            "name": "source_url",
            "source": "/document/metadata_storage_path"
          }
        ]
      },
      {
        "targetIndexName": "rag-psegtechm-index-vnext",
        "parentKeyFieldName": "image_document_id",
        "sourceContext": "/document/normalized_images/*",
        "mappings": [
          {
            "name": "record_type",
            "source": "='image'"
          },
          {
            "name": "content_text",
            "source": "/document/normalized_images/*/imageSearchText"
          },
          {
            "name": "content_embedding",
            "source": "/document/normalized_images/*/image_vector"
          },
          {
            "name": "content_path",
            "source": "/document/normalized_images/*/imagePath"
          },
          {
            "name": "page_number",
            "source": "/document/normalized_images/*/locationMetadata/pageNumber"
          },
          {
            "name": "bounding_polygons",
            "source": "/document/normalized_images/*/locationMetadata/boundingPolygons"
          },
          {
            "name": "document_title",
            "source": "/document/metadata_storage_name"
          },
          {
            "name": "source_file",
            "source": "/document/metadata_storage_name"
          },
          {
            "name": "source_url",
            "source": "/document/metadata_storage_path"
          }
        ]
      }
    ],
    "parameters": {
      "projectionMode": "skipIndexingParentDocuments"
    }
  },
  "knowledgeStore": {
    "storageConnectionString": "<STORAGE_CONN_STR>",
    "projections": [
      {
        "files": [
          {
            "storageContainer": "pseg-techm-images-vnext",
            "source": "/document/normalized_images/*"
          }
        ]
      }
    ]
  }
}

### INDEXER

{
  "name": "pseg-techm-indexer-vnext",
  "dataSourceName": "pseg-techm-blob-ds-vnext",
  "targetIndexName": "rag-psegtechm-index-vnext",
  "skillsetName": "pseg-techm-skillset-vnext",
  "parameters": {
    "batchSize": 1,
    "maxFailedItems": -1,
    "maxFailedItemsPerBatch": -1,
    "configuration": {
      "dataToExtract": "contentAndMetadata",
      "parsingMode": "default",
      "allowSkillsetToReadFileData": true,
      "imageAction": "generateNormalizedImages",
      "failOnUnsupportedContentType": false,
      "failOnUnprocessableDocument": false
    }
  },
  "fieldMappings": [],
  "outputFieldMappings": []
}


