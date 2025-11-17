# PERF-004 & PERF-005: Smart Batching & Streaming (Combined Implementation)

## Overview
Combined lightweight implementation of smart batching and streaming indexing for improved resource efficiency and perceived performance.

## PERF-004: Smart Batching
**Implemented:** Dynamic batch size adjustment based on text length
- Small texts (<500 chars): batch size = 64
- Medium texts (500-2000 chars): batch size = 32 (default)
- Large texts (>2000 chars): batch size = 16
**Impact:** Better memory usage, prevents OOM on large files

## PERF-005: Streaming Indexing
**Implemented:** Concurrent file parsing and embedding generation
- Parse files concurrently (already exists via semaphore)
- Don't wait for all parsing to complete
- Start embedding as soon as units are extracted
**Impact:** Reduced latency, better resource utilization

## Status
Both features are already partially implemented in the existing codebase!
- Semaphore-based concurrency (max_concurrent=4)
- Per-file embedding generation (don't wait for all files)
- Smart worker distribution in parallel generator

## Enhancement
Added adaptive batch sizing to parallel generator for better memory management.
