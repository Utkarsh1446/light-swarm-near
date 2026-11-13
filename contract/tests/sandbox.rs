//! Sandbox integration: real wasm, real receipts, sub-accounts, and a
//! function-call key that cannot call `cancel`.

use std::process::Command;

use near_workspaces::types::{AccessKey, KeyType, NearToken, SecretKey};
use near_workspaces::Account;
use serde_json::json;

const ANSWER: &str = "dc0be30dfb22566bbd5cdb3cc68c0617305d13377a3107320d87e3d86384c9a6";
const COMMIT: &str = "32001f14d790be3047995d91e37743245991f57c932807fcbbb73ecff0bfd690";
const ONE: u128 = 1_000_000_000_000_000_000_000_000;
const TENTH: u128 = 100_000_000_000_000_000_000_000;

#[tokio::test]
async fn sandbox_pays_the_solver_and_limits_agent_keys() -> anyhow::Result<()> {
    let wasm = build_wasm();
    // near-workspaces 0.22 uses near-sandbox 2.10.0, which can prepare this wasm.
    let worker = near_workspaces::sandbox().await?;
    let contract = worker.dev_deploy(&wasm).await?;
    contract
        .call("new")
        .args_json(json!({"max_stake": ONE.to_string()}))
        .max_gas()
        .transact()
        .await?
        .into_result()?;

    let requester = worker.dev_create_account().await?;
    let geo = requester
        .create_subaccount("geo")
        .initial_balance(NearToken::from_near(20))
        .keys(SecretKey::from_seed(KeyType::ED25519, "geo-full"))
        .transact()
        .await?
        .into_result()?;
    let limited_key = SecretKey::from_seed(KeyType::ED25519, "obj-limited");
    let obj = requester
        .create_subaccount("obj")
        .initial_balance(NearToken::from_near(20))
        .keys(SecretKey::from_seed(KeyType::ED25519, "obj-full"))
        .transact()
        .await?
        .into_result()?;
    obj.batch(obj.id())
        .add_key(
            limited_key.public_key(),
            AccessKey::function_call_access(
                contract.id(),
                &["register_agent", "place_bid", "commit_solution", "reveal_solution", "subcontract"],
                Some(NearToken::from_near(2)),
            ),
        )
        .transact()
        .await?
        .into_result()?;
    let obj_limited = Account::from_secret_key(obj.id().clone(), limited_key, &worker);

    geo.call(contract.id(), "register_agent").max_gas().transact().await?.into_result()?;
    let before = geo.view_account().await?.balance.as_yoctonear();

    let task_id: u64 = requester
        .call(contract.id(), "post_task")
        .args_json(json!({
            "demos": "12;30|12;30",
            "test_input": "12;30",
            "answer_hash": ANSWER,
            "stake_required": TENTH.to_string(),
            "window": 8
        }))
        .deposit(NearToken::from_yoctonear(ONE))
        .max_gas()
        .transact()
        .await?
        .into_result()?
        .json()?;

    geo.call(contract.id(), "place_bid")
        .args_json(json!({
            "task_id": task_id,
            "price": (4 * TENTH).to_string(),
            "confidence_bps": 8000
        }))
        .deposit(NearToken::from_yoctonear(TENTH))
        .max_gas()
        .transact()
        .await?
        .into_result()?;

    requester
        .call(contract.id(), "assign_best")
        .args_json(json!({"task_id": task_id}))
        .max_gas()
        .transact()
        .await?
        .into_result()?;

    geo.call(contract.id(), "commit_solution")
        .args_json(json!({"task_id": task_id, "commit_hash": COMMIT}))
        .max_gas()
        .transact()
        .await?
        .into_result()?;

    let reveal = geo
        .call(contract.id(), "reveal_solution")
        .args_json(json!({"task_id": task_id, "output": "12;30", "salt": "abc"}))
        .max_gas()
        .transact()
        .await?
        .into_result()?;
    let reveal_json: serde_json::Value = reveal.json()?;
    assert_eq!(reveal_json["correct"], true);
    assert_eq!(reveal_json["solver_paid"], (4 * TENTH).to_string());
    assert_eq!(reveal_json["requester_refund"], (6 * TENTH).to_string());

    let agent: serde_json::Value = contract
        .view("get_agent")
        .args_json(json!({"account": geo.id()}))
        .await?
        .json()?;
    assert_eq!(agent["reputation"], 1080);
    assert_eq!(agent["solves"], 1);
    assert_eq!(agent["account"], geo.id().as_str());
    assert!(geo.id().as_str().ends_with(&format!(".{}", requester.id())));

    let after = geo.view_account().await?.balance.as_yoctonear();
    assert!(after > before, "solver should be up by the price minus gas, before {before} after {after}");

    let denied = obj_limited
        .call(contract.id(), "cancel")
        .args_json(json!({"task_id": task_id}))
        .max_gas()
        .transact()
        .await;
    match denied {
        Ok(result) => assert!(result.is_failure(), "function-call key must not be able to cancel: {result:?}"),
        Err(err) => {
            let mut text = format!("{err:?}").to_lowercase();
            let mut source = std::error::Error::source(&err);
            while let Some(inner) = source {
                text.push(' ');
                text.push_str(&format!("{inner}").to_lowercase());
                source = std::error::Error::source(inner);
            }
            assert!(
                text.contains("method")
                    || text.contains("access key")
                    || text.contains("permission")
                    || text.contains("not allowed"),
                "function-call key must not be able to cancel: {text}"
            );
        }
    }

    obj_limited
        .call(contract.id(), "register_agent")
        .max_gas()
        .transact()
        .await?
        .into_result()?;
    let registered: serde_json::Value = contract
        .view("get_agent")
        .args_json(json!({"account": obj.id()}))
        .await?
        .json()?;
    assert_eq!(registered["reputation"], 1000);

    Ok(())
}

fn build_wasm() -> Vec<u8> {
    let manifest = concat!(env!("CARGO_MANIFEST_DIR"), "/Cargo.toml");
    let target_dir = std::env::temp_dir().join("light-swarm-wasm");
    let status = Command::new("cargo")
        .args(["build", "--release", "--target", "wasm32-unknown-unknown", "--manifest-path", manifest])
        .env("CARGO_TARGET_DIR", &target_dir)
        .status()
        .expect("cargo wasm build");
    assert!(status.success(), "wasm build failed");
    let path = target_dir.join("wasm32-unknown-unknown/release/light_swarm_market.wasm");
    std::fs::read(&path).unwrap_or_else(|err| panic!("read {}: {err}", path.display()))
}
