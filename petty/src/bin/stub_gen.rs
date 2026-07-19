use pyo3_stub_gen::Result;

fn main() -> Result<()> {
    let stub = _petty::stub_info()?;
    stub.generate()?;
    Ok(())
}
