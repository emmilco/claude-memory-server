use pyo3::prelude::*;

mod parsing;

/// Normalize a batch of embeddings to unit length.
///
/// Args:
///     embeddings: List of embedding vectors
///
/// Returns:
///     List of normalized embedding vectors
#[pyfunction]
fn batch_normalize_embeddings(embeddings: Vec<Vec<f32>>) -> PyResult<Vec<Vec<f32>>> {
    Ok(embeddings
        .iter()
        .map(|emb| {
            let norm: f32 = emb.iter().map(|x| x * x).sum::<f32>().sqrt();
            if norm > 0.0 {
                emb.iter().map(|x| x / norm).collect()
            } else {
                vec![0.0; emb.len()]
            }
        })
        .collect())
}

/// Calculate cosine similarity between two vectors.
///
/// Args:
///     vec_a: First vector
///     vec_b: Second vector
///
/// Returns:
///     Cosine similarity score (0.0 to 1.0)
#[pyfunction]
fn cosine_similarity(vec_a: Vec<f32>, vec_b: Vec<f32>) -> PyResult<f32> {
    if vec_a.len() != vec_b.len() {
        return Err(pyo3::exceptions::PyValueError::new_err(
            "Vectors must have the same length",
        ));
    }

    let dot_product: f32 = vec_a.iter().zip(vec_b.iter()).map(|(a, b)| a * b).sum();

    let norm_a: f32 = vec_a.iter().map(|x| x * x).sum::<f32>().sqrt();
    let norm_b: f32 = vec_b.iter().map(|x| x * x).sum::<f32>().sqrt();

    if norm_a == 0.0 || norm_b == 0.0 {
        return Ok(0.0);
    }

    Ok(dot_product / (norm_a * norm_b))
}

/// Python module for high-performance operations.
#[pymodule]
fn mcp_performance_core(m: &Bound<'_, PyModule>) -> PyResult<()> {
    // Embedding operations
    m.add_function(wrap_pyfunction!(batch_normalize_embeddings, m)?)?;
    m.add_function(wrap_pyfunction!(cosine_similarity, m)?)?;

    // Parsing operations
    m.add_function(wrap_pyfunction!(parsing::parse_source_file, m)?)?;
    m.add_function(wrap_pyfunction!(parsing::batch_parse_files, m)?)?;
    m.add_class::<parsing::SemanticUnit>()?;
    m.add_class::<parsing::ParseResult>()?;

    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_batch_normalize() {
        let input = vec![vec![3.0, 4.0], vec![5.0, 12.0]];
        let result = batch_normalize_embeddings(input).unwrap();

        // First vector: [3, 4] -> norm = 5 -> [0.6, 0.8]
        assert!((result[0][0] - 0.6).abs() < 0.001);
        assert!((result[0][1] - 0.8).abs() < 0.001);

        // Second vector: [5, 12] -> norm = 13 -> [5/13, 12/13]
        assert!((result[1][0] - 5.0 / 13.0).abs() < 0.001);
        assert!((result[1][1] - 12.0 / 13.0).abs() < 0.001);
    }

    #[test]
    fn test_cosine_similarity_identical() {
        let vec = vec![1.0, 2.0, 3.0];
        let similarity = cosine_similarity(vec.clone(), vec).unwrap();
        assert!((similarity - 1.0).abs() < 0.001);
    }

    #[test]
    fn test_cosine_similarity_orthogonal() {
        let vec_a = vec![1.0, 0.0];
        let vec_b = vec![0.0, 1.0];
        let similarity = cosine_similarity(vec_a, vec_b).unwrap();
        assert!((similarity - 0.0).abs() < 0.001);
    }
}
