import sys

def patch_account():
    filepath = 'c:/Users/User/Desktop/AvokProject/frontend/app/(dashboard)/account/page.jsx'
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # Add State for admin phonenumber input
    if "const [adminPhone, setAdminPhone] = useState" not in content:
        content = content.replace(
            "const [allocating, setAllocating] = useState(false);",
            "const [allocating, setAllocating] = useState(false);\n  const [adminPhone, setAdminPhone] = useState(\"\");"
        )

    # Insert Admin Widget Right AFTER the KYC section
    new_widget = """        </section>

        {user?.role === 'super_admin' && (
          <section className="card rounded-[28px] bg-rose-50 p-6 border border-rose-200 mt-4 xl:col-span-2">
            <h3 className="text-xl font-bold text-rose-900">Super Admin Zone: Role Management</h3>
            <p className="mt-2 text-sm text-rose-700">Appoint or dismiss administrators securely.</p>
            <div className="mt-4 flex flex-col sm:flex-row gap-3">
              <input 
                className="field flex-1" 
                placeholder="Target User Phone Number (e.g. 0241234567)" 
                value={adminPhone}
                onChange={(e) => setAdminPhone(e.target.value)}
              />
              <button 
                type="button" 
                className="btn-primary bg-emerald-700 hover:bg-emerald-800 focus:ring-emerald-600 text-white" 
                onClick={async () => {
                  try {
                    await api.post("/auth/roles/appoint-admin", { phone_number: adminPhone });
                    alert("Admin Appointed Successfully!");
                    setAdminPhone("");
                  } catch (e) {
                    alert(e.response?.data?.detail || e.message);
                  }
                }}
              >
                Appoint Admin
              </button>
              <button 
                type="button" 
                className="btn-primary bg-rose-700 hover:bg-rose-800 focus:ring-rose-600 text-white" 
                onClick={async () => {
                  try {
                    await api.post("/auth/roles/dismiss-admin", { phone_number: adminPhone });
                    alert("Admin Dismissed Successfully!");
                    setAdminPhone("");
                  } catch (e) {
                    alert(e.response?.data?.detail || e.message);
                  }
                }}
              >
                Dismiss Admin
              </button>
            </div>
          </section>
        )}
      </div>
    </div>
  );
}"""
    
    old_end = """        </section>
      </div>
    </div>
  );
}"""

    if old_end in content:
        content = content.replace(old_end, new_widget)
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)

if __name__ == "__main__":
    patch_account()
    print("Patched React Super Admin frontend.")
