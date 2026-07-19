use pyo3::prelude::*;

#[pyclass]
struct MyClass {}

#[pymodule]
mod my_module {
    use super::*;
    #[pymodule_export]
    use super::MyClass;
}
