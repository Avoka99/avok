import sys

def patch_account():
    filepath = 'c:/Users/User/Desktop/AvokProject/frontend/app/(dashboard)/account/page.jsx'
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # Generic wording
    if "Verified Avok account</p>" in content:
        content = content.replace("Verified Avok account</p>", "Verify Account</p>")

    # Form state
    old_state = """    ghana_card_number: "",
    bank_or_momo_target: "টার","""
    # Oops wait, I don't need to regex this perfectly, let's just replace the whole block or specific lines.
    
    old_fields_state = """    ghana_card_number: "",
    bank_or_momo_target: """
    new_fields_state = """    document_type: "ghana_card",
    document_number: "",
    bank_or_momo_target: """
    if old_fields_state in content:
        content = content.replace(old_fields_state, new_fields_state)
        
    old_ghana_input = """            <input
              className="field"
              placeholder="Ghana Card number"
              value={profile.ghana_card_number}
              onChange={(event) => setProfile((prev) => ({ ...prev, ghana_card_number: event.target.value }))}
            />"""
            
    new_doc_inputs = """            <select
              className="field"
              value={profile.document_type}
              onChange={(event) => setProfile((prev) => ({ ...prev, document_type: event.target.value }))}
            >
              <option value="ghana_card">Ghana Card</option>
              <option value="voter_id">Voter ID</option>
              <option value="driver_license">Driver License</option>
              <option value="national_id">Other National ID</option>
            </select>
            <input
              className="field"
              placeholder="Document Number (add 999 to simulate fraud)"
              value={profile.document_number}
              onChange={(event) => setProfile((prev) => ({ ...prev, document_number: event.target.value }))}
            />"""
            
    if old_ghana_input in content:
        content = content.replace(old_ghana_input, new_doc_inputs)

    # Submit button update
    old_btn = """          <button type="button" className="btn-primary mt-5 w-full">
            Submit verification details
          </button>"""
    new_btn = """          <button type="button" className="btn-primary mt-5 w-full" onClick={async () => {
              try {
                  await api.post("/auth/kyc", {
                      document_type: profile.document_type,
                      document_number: profile.document_number,
                      document_image: "dummy_image_url",
                      selfie_image: "dummy_selfie_url"
                  });
                  alert("KYC Submitted! Admins will review it.");
              } catch(e) {
                  alert(e.response?.data?.detail || e.message);
              }
          }}>
            Submit verification details
          </button>"""
          
    if old_btn in content:
        content = content.replace(old_btn, new_btn)

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)

if __name__ == "__main__":
    patch_account()
    print("Patched React KYC frontend.")
