//! Light Agents swarm market.
//!
//! A requester escrows a bounty. Agents stake, bid a price and a confidence, and
//! may be assigned. The assignee commits to an output grid, then reveals it in a
//! later block. The contract pays only when `sha256(grid)` matches the hash
//! posted with the task. A wrong reveal slashes the stake and reopens the task.
//! One helper can be hired for at most half the price.
//!
//! This is the wasm half of the rules in `swarm/market.py`. Amounts are yoctoNEAR.

use near_sdk::json_types::U128;
use near_sdk::{env, near, require, AccountId, NearToken, Promise};

const REP_INIT: u64 = 1000;
const REP_SOLVE_BASE: u64 = 40;
const REP_CONF_DIV: u64 = 200;
const REP_HELPER: u64 = 20;
const REP_FAIL: u64 = 60;
const MAX_BIDS: usize = 8;
const MAX_SHARE_BPS: u16 = 5000;
const MAX_SIDE: usize = 30;
const MAX_STRING: usize = 2000;
const MAX_TASKS: u64 = 128;
const MIN_WINDOW: u64 = 2;
const MAX_WINDOW: u64 = 10_000;

#[near(serializers = [borsh, json])]
#[derive(Clone)]
pub struct Bid {
    pub bidder: AccountId,
    pub price: u128,
    pub confidence_bps: u16,
    pub stake: u128,
    pub slashed: bool,
    pub refunded: bool,
}

#[near(serializers = [borsh, json])]
#[derive(Clone)]
pub struct Attempt {
    pub assignee: AccountId,
    pub correct: bool,
    pub slashed: u128,
    pub reason: String,
}

#[near(serializers = [borsh, json])]
#[derive(Clone)]
pub struct Task {
    pub task_id: u64,
    pub requester: AccountId,
    pub demos: String,
    pub test_input: String,
    pub answer_hash: String,
    pub bounty: u128,
    pub stake_required: u128,
    pub window: u64,
    pub status: String,
    pub assignee: Option<AccountId>,
    pub deadline_block: u64,
    pub commit_hash: Option<String>,
    pub commit_block: u64,
    pub helper: Option<AccountId>,
    pub share_bps: u16,
    pub bids: Vec<Bid>,
    pub attempts: Vec<Attempt>,
    pub solver_paid: u128,
    pub helper_paid: u128,
    pub requester_refund: u128,
    pub slash_paid: u128,
}

#[near(serializers = [borsh, json])]
#[derive(Clone)]
pub struct Agent {
    pub account: AccountId,
    pub reputation: u64,
    pub solves: u32,
    pub fails: u32,
    pub earned: u128,
    pub slashed: u128,
}

#[near(serializers = [borsh, json])]
#[derive(Clone)]
pub struct RevealResult {
    pub correct: bool,
    pub slashed: U128,
    pub reason: String,
    pub solver_paid: U128,
    pub helper_paid: U128,
    pub requester_refund: U128,
}

#[near(serializers = [json])]
#[derive(Clone)]
pub struct BidView {
    pub bidder: AccountId,
    pub price: U128,
    pub confidence_bps: u16,
    pub stake: U128,
    pub slashed: bool,
    pub refunded: bool,
}

#[near(serializers = [json])]
#[derive(Clone)]
pub struct AttemptView {
    pub assignee: AccountId,
    pub correct: bool,
    pub slashed: U128,
    pub reason: String,
}

#[near(serializers = [json])]
#[derive(Clone)]
pub struct TaskView {
    pub task_id: u64,
    pub requester: AccountId,
    pub demos: String,
    pub test_input: String,
    pub answer_hash: String,
    pub bounty: U128,
    pub stake_required: U128,
    pub window: u64,
    pub status: String,
    pub assignee: Option<AccountId>,
    pub deadline_block: u64,
    pub helper: Option<AccountId>,
    pub share_bps: u16,
    pub bids: Vec<BidView>,
    pub attempts: Vec<AttemptView>,
    pub solver_paid: U128,
    pub helper_paid: U128,
    pub requester_refund: U128,
    pub slash_paid: U128,
}

#[near(serializers = [json])]
#[derive(Clone)]
pub struct AgentView {
    pub account: AccountId,
    pub reputation: u64,
    pub solves: u32,
    pub fails: u32,
    pub earned: U128,
    pub slashed: U128,
}

#[near(serializers = [borsh, json])]
#[derive(Clone)]
pub struct Stats {
    pub tasks_posted: u64,
    pub tasks_solved: u64,
    pub total_slashed: U128,
    pub total_paid: U128,
    pub agents: u64,
    pub max_stake: U128,
}

#[near(contract_state)]
pub struct Market {
    owner: AccountId,
    max_stake: u128,
    task_count: u64,
    tasks: Vec<Task>,
    agents: Vec<Agent>,
    tasks_solved: u64,
    total_slashed: u128,
    total_paid: u128,
}

#[near]
impl Market {
    #[init]
    pub fn new(max_stake: U128) -> Self {
        require!(max_stake.0 > 0, "max stake required");
        Self {
            owner: env::predecessor_account_id(),
            max_stake: max_stake.0,
            task_count: 0,
            tasks: Vec::new(),
            agents: Vec::new(),
            tasks_solved: 0,
            total_slashed: 0,
            total_paid: 0,
        }
    }

    pub fn register_agent(&mut self) {
        self.ensure_agent(env::predecessor_account_id());
    }

    pub fn set_max_stake(&mut self, max_stake: U128) {
        require!(env::predecessor_account_id() == self.owner, "only owner");
        require!(max_stake.0 > 0, "max stake required");
        self.max_stake = max_stake.0;
    }

    #[payable]
    pub fn post_task(
        &mut self,
        demos: String,
        test_input: String,
        answer_hash: String,
        stake_required: U128,
        window: u64,
    ) -> u64 {
        require!(self.task_count < MAX_TASKS, "task cap");
        let bounty = env::attached_deposit().as_yoctonear();
        require!(bounty > 0, "bounty required");
        require!(stake_required.0 > 0 && stake_required.0 <= self.max_stake, "bad stake");
        require!(window >= MIN_WINDOW && window <= MAX_WINDOW, "bad window");
        require!(is_lower_hex64(&answer_hash), "bad answer hash");
        require!(valid_grid(&test_input), "bad grid");
        require!(valid_demos(&demos), "bad demos");
        let requester = env::predecessor_account_id();
        self.task_count += 1;
        let task_id = self.task_count;
        let block = env::block_height();
        self.tasks.push(Task {
            task_id,
            requester: requester.clone(),
            demos,
            test_input,
            answer_hash,
            bounty,
            stake_required: stake_required.0,
            window,
            status: "open".to_string(),
            assignee: None,
            deadline_block: block + window,
            commit_hash: None,
            commit_block: 0,
            helper: None,
            share_bps: 0,
            bids: Vec::new(),
            attempts: Vec::new(),
            solver_paid: 0,
            helper_paid: 0,
            requester_refund: 0,
            slash_paid: 0,
        });
        emit("post_task", &format!("{{\"task_id\":{task_id},\"requester\":\"{requester}\",\"bounty\":\"{bounty}\"}}"));
        task_id
    }

    #[payable]
    pub fn place_bid(&mut self, task_id: u64, price: U128, confidence_bps: u16) {
        let index = self.open_index(task_id);
        let bidder = env::predecessor_account_id();
        let stake = env::attached_deposit().as_yoctonear();
        require!(bidder != self.tasks[index].requester, "requester cannot bid");
        require!((1..=10_000).contains(&confidence_bps), "bad confidence");
        require!(price.0 > 0 && price.0 <= self.tasks[index].bounty, "bad price");
        require!(stake >= self.tasks[index].stake_required && stake <= self.max_stake, "bad stake");
        require!(self.tasks[index].bids.iter().all(|bid| bid.bidder != bidder), "bid exists");
        require!(self.tasks[index].bids.len() < MAX_BIDS, "bid cap");
        self.ensure_agent(bidder.clone());
        self.tasks[index].bids.push(Bid {
            bidder: bidder.clone(),
            price: price.0,
            confidence_bps,
            stake,
            slashed: false,
            refunded: false,
        });
        emit("place_bid", &format!("{{\"task_id\":{task_id},\"bidder\":\"{bidder}\",\"price\":\"{}\"}}", price.0));
    }

    pub fn assign_best(&mut self, task_id: u64) -> bool {
        let index = self.task_index(task_id);
        require!(env::predecessor_account_id() == self.tasks[index].requester, "only requester assigns");
        require!(self.tasks[index].status == "open", "task not open");
        let Some(choice) = self.best_bid_index(index) else {
            return false;
        };
        let assignee = self.tasks[index].bids[choice].bidder.clone();
        let task = &mut self.tasks[index];
        task.assignee = Some(assignee.clone());
        task.status = "assigned".to_string();
        task.commit_hash = None;
        task.commit_block = 0;
        task.helper = None;
        task.share_bps = 0;
        task.deadline_block = env::block_height() + task.window;
        emit("assign", &format!("{{\"task_id\":{task_id},\"assignee\":\"{assignee}\"}}"));
        true
    }

    pub fn subcontract(&mut self, task_id: u64, helper: AccountId, share_bps: u16) {
        let index = self.assigned_index(task_id, &env::predecessor_account_id());
        require!(self.tasks[index].helper.is_none(), "subcontract exists");
        let assignee = self.tasks[index].assignee.clone().unwrap();
        require!(helper != assignee && helper != self.tasks[index].requester, "bad helper");
        require!(self.agent_index(&helper).is_some(), "helper not registered");
        require!(share_bps >= 1 && share_bps <= MAX_SHARE_BPS, "bad share");
        self.tasks[index].helper = Some(helper.clone());
        self.tasks[index].share_bps = share_bps;
        emit("subcontract", &format!("{{\"task_id\":{task_id},\"helper\":\"{helper}\",\"share_bps\":{share_bps}}}"));
    }

    pub fn commit_solution(&mut self, task_id: u64, commit_hash: String) {
        let index = self.assigned_index(task_id, &env::predecessor_account_id());
        require!(self.tasks[index].commit_hash.is_none(), "already committed");
        require!(is_lower_hex64(&commit_hash), "bad commitment");
        self.tasks[index].commit_hash = Some(commit_hash);
        self.tasks[index].commit_block = env::block_height();
        emit("commit_solution", &format!("{{\"task_id\":{task_id}}}"));
    }

    pub fn reveal_solution(&mut self, task_id: u64, output: String, salt: String) -> RevealResult {
        let caller = env::predecessor_account_id();
        let index = self.assigned_index(task_id, &caller);
        require!(self.tasks[index].commit_hash.is_some(), "no commit");
        require!(env::block_height() > self.tasks[index].commit_block, "reveal too early");
        require!(valid_salt(&salt) && valid_grid(&output), "bad reveal");
        let commit_ok = sha256_hex(format!("{output}|{salt}").as_bytes()) == self.tasks[index].commit_hash.clone().unwrap();
        let answer_ok = sha256_hex(output.as_bytes()) == self.tasks[index].answer_hash;
        if !commit_ok || !answer_ok {
            let reason = if !commit_ok { "commit_mismatch" } else { "wrong_answer" };
            let slashed = self.slash(index, reason);
            return RevealResult {
                correct: false,
                slashed: U128(slashed),
                reason: reason.to_string(),
                solver_paid: U128(0),
                helper_paid: U128(0),
                requester_refund: U128(0),
            };
        }
        self.pay(index)
    }

    pub fn cancel(&mut self, task_id: u64) {
        let index = self.task_index(task_id);
        let caller = env::predecessor_account_id();
        require!(caller == self.tasks[index].requester, "only requester cancels");
        require!(self.tasks[index].status == "open", "task not open");
        let bounty = self.tasks[index].bounty;
        let requester = self.tasks[index].requester.clone();
        transfer(requester, bounty);
        self.tasks[index].requester_refund += bounty;
        let refunds: Vec<(AccountId, u128)> = self.tasks[index]
            .bids
            .iter()
            .filter(|bid| !bid.slashed && !bid.refunded)
            .map(|bid| (bid.bidder.clone(), bid.stake))
            .collect();
        for bid in &mut self.tasks[index].bids {
            if !bid.slashed && !bid.refunded {
                bid.refunded = true;
            }
        }
        for (bidder, stake) in refunds {
            transfer(bidder, stake);
        }
        self.tasks[index].status = "cancelled".to_string();
        emit("cancel", &format!("{{\"task_id\":{task_id}}}"));
    }

    pub fn slash_timeout(&mut self, task_id: u64) {
        let index = self.task_index(task_id);
        require!(self.tasks[index].status == "assigned" && self.tasks[index].assignee.is_some(), "task not assigned");
        require!(env::block_height() > self.tasks[index].deadline_block, "deadline not reached");
        self.slash(index, "timeout");
    }

    pub fn get_task(&self, task_id: u64) -> TaskView {
        let task = self.tasks.iter().find(|task| task.task_id == task_id).expect("task not found");
        TaskView {
            task_id: task.task_id,
            requester: task.requester.clone(),
            demos: task.demos.clone(),
            test_input: task.test_input.clone(),
            answer_hash: task.answer_hash.clone(),
            bounty: U128(task.bounty),
            stake_required: U128(task.stake_required),
            window: task.window,
            status: task.status.clone(),
            assignee: task.assignee.clone(),
            deadline_block: task.deadline_block,
            helper: task.helper.clone(),
            share_bps: task.share_bps,
            bids: task
                .bids
                .iter()
                .map(|bid| BidView {
                    bidder: bid.bidder.clone(),
                    price: U128(bid.price),
                    confidence_bps: bid.confidence_bps,
                    stake: U128(bid.stake),
                    slashed: bid.slashed,
                    refunded: bid.refunded,
                })
                .collect(),
            attempts: task
                .attempts
                .iter()
                .map(|attempt| AttemptView {
                    assignee: attempt.assignee.clone(),
                    correct: attempt.correct,
                    slashed: U128(attempt.slashed),
                    reason: attempt.reason.clone(),
                })
                .collect(),
            solver_paid: U128(task.solver_paid),
            helper_paid: U128(task.helper_paid),
            requester_refund: U128(task.requester_refund),
            slash_paid: U128(task.slash_paid),
        }
    }

    pub fn get_agent(&self, account: AccountId) -> AgentView {
        let agent = self.agents.iter().find(|agent| agent.account == account).expect("agent not registered");
        AgentView {
            account: agent.account.clone(),
            reputation: agent.reputation,
            solves: agent.solves,
            fails: agent.fails,
            earned: U128(agent.earned),
            slashed: U128(agent.slashed),
        }
    }

    pub fn get_agents(&self) -> Vec<AgentView> {
        self.agents
            .iter()
            .map(|agent| AgentView {
                account: agent.account.clone(),
                reputation: agent.reputation,
                solves: agent.solves,
                fails: agent.fails,
                earned: U128(agent.earned),
                slashed: U128(agent.slashed),
            })
            .collect()
    }

    pub fn get_stats(&self) -> Stats {
        Stats {
            tasks_posted: self.task_count,
            tasks_solved: self.tasks_solved,
            total_slashed: U128(self.total_slashed),
            total_paid: U128(self.total_paid),
            agents: self.agents.len() as u64,
            max_stake: U128(self.max_stake),
        }
    }
}

impl Market {
    fn pay(&mut self, index: usize) -> RevealResult {
        let assignee = self.tasks[index].assignee.clone().unwrap();
        let bid_index = self.bid_index(index, &assignee);
        let price = self.tasks[index].bids[bid_index].price;
        let confidence = self.tasks[index].bids[bid_index].confidence_bps;
        let share = self.tasks[index].share_bps;
        let helper = self.tasks[index].helper.clone();
        let cut = if helper.is_some() { price * u128::from(share) / 10_000 } else { 0 };
        let solver_paid = price - cut;
        let refund = self.tasks[index].bounty - price;
        let requester = self.tasks[index].requester.clone();

        transfer(assignee.clone(), solver_paid);
        if let Some(helper_id) = helper.clone() {
            if cut > 0 {
                transfer(helper_id.clone(), cut);
            }
            let helper_agent = self.agent_index(&helper_id).unwrap();
            self.agents[helper_agent].reputation += REP_HELPER;
            self.agents[helper_agent].earned += cut;
        }
        if refund > 0 {
            transfer(requester, refund);
        }
        let stakes: Vec<(AccountId, u128)> = self.tasks[index]
            .bids
            .iter()
            .filter(|bid| !bid.slashed && !bid.refunded)
            .map(|bid| (bid.bidder.clone(), bid.stake))
            .collect();
        for bid in &mut self.tasks[index].bids {
            if !bid.slashed && !bid.refunded {
                bid.refunded = true;
            }
        }
        for (bidder, stake) in stakes {
            transfer(bidder, stake);
        }

        let agent = self.agent_index(&assignee).unwrap();
        self.agents[agent].reputation += REP_SOLVE_BASE + u64::from(confidence) / REP_CONF_DIV;
        self.agents[agent].solves += 1;
        self.agents[agent].earned += solver_paid;

        let task = &mut self.tasks[index];
        task.solver_paid = solver_paid;
        task.helper_paid = cut;
        task.requester_refund += refund;
        task.status = "solved".to_string();
        task.attempts.push(Attempt {
            assignee: assignee.clone(),
            correct: true,
            slashed: 0,
            reason: "solved".to_string(),
        });
        self.tasks_solved += 1;
        self.total_paid += solver_paid + cut;
        let task_id = self.tasks[index].task_id;
        emit("reveal_solution", &format!("{{\"task_id\":{task_id},\"correct\":true,\"solver\":\"{assignee}\",\"solver_paid\":\"{solver_paid}\"}}"));
        RevealResult {
            correct: true,
            slashed: U128(0),
            reason: "solved".to_string(),
            solver_paid: U128(solver_paid),
            helper_paid: U128(cut),
            requester_refund: U128(refund),
        }
    }

    fn slash(&mut self, index: usize, reason: &str) -> u128 {
        let assignee = self.tasks[index].assignee.clone().unwrap();
        let bid_index = self.bid_index(index, &assignee);
        require!(!self.tasks[index].bids[bid_index].slashed, "already slashed");
        let stake = self.tasks[index].bids[bid_index].stake;
        let requester = self.tasks[index].requester.clone();
        transfer(requester, stake);
        self.tasks[index].bids[bid_index].slashed = true;
        let agent = self.agent_index(&assignee).unwrap();
        self.agents[agent].reputation = self.agents[agent].reputation.saturating_sub(REP_FAIL);
        self.agents[agent].fails += 1;
        self.agents[agent].slashed += stake;
        let task = &mut self.tasks[index];
        task.slash_paid += stake;
        task.attempts.push(Attempt {
            assignee: assignee.clone(),
            correct: false,
            slashed: stake,
            reason: reason.to_string(),
        });
        task.assignee = None;
        task.commit_hash = None;
        task.commit_block = 0;
        task.helper = None;
        task.share_bps = 0;
        task.status = "open".to_string();
        self.total_slashed += stake;
        let task_id = task.task_id;
        emit("slash", &format!("{{\"task_id\":{task_id},\"assignee\":\"{assignee}\",\"reason\":\"{reason}\",\"stake\":\"{stake}\"}}"));
        stake
    }

    fn best_bid_index(&self, task_index: usize) -> Option<usize> {
        let mut best: Option<(usize, u128, u128, AccountId)> = None;
        for (index, bid) in self.tasks[task_index].bids.iter().enumerate() {
            if bid.slashed {
                continue;
            }
            let reputation = self.agents.iter().find(|agent| agent.account == bid.bidder).unwrap().reputation;
            let score = u128::from(bid.confidence_bps) * u128::from(reputation) / bid.price;
            let better = match &best {
                None => true,
                Some((_, best_score, best_price, best_account)) => {
                    score > *best_score
                        || (score == *best_score && (bid.price < *best_price || (bid.price == *best_price && bid.bidder < *best_account)))
                }
            };
            if better {
                best = Some((index, score, bid.price, bid.bidder.clone()));
            }
        }
        best.map(|(index, _, _, _)| index)
    }

    fn ensure_agent(&mut self, account: AccountId) {
        if self.agent_index(&account).is_none() {
            self.agents.push(Agent {
                account,
                reputation: REP_INIT,
                solves: 0,
                fails: 0,
                earned: 0,
                slashed: 0,
            });
        }
    }

    fn agent_index(&self, account: &AccountId) -> Option<usize> {
        self.agents.iter().position(|agent| &agent.account == account)
    }

    fn task_index(&self, task_id: u64) -> usize {
        self.tasks.iter().position(|task| task.task_id == task_id).expect("task not found")
    }

    fn open_index(&self, task_id: u64) -> usize {
        let index = self.task_index(task_id);
        require!(self.tasks[index].status == "open", "task not open");
        index
    }

    fn assigned_index(&self, task_id: u64, assignee: &AccountId) -> usize {
        let index = self.task_index(task_id);
        require!(self.tasks[index].status == "assigned" && self.tasks[index].assignee.as_ref() == Some(assignee), "not assignee");
        index
    }

    fn bid_index(&self, task_index: usize, bidder: &AccountId) -> usize {
        self.tasks[task_index].bids.iter().position(|bid| &bid.bidder == bidder).expect("bid missing")
    }
}

impl Default for Market {
    fn default() -> Self {
        Self {
            owner: "owner.near".parse().unwrap(),
            max_stake: 1,
            task_count: 0,
            tasks: Vec::new(),
            agents: Vec::new(),
            tasks_solved: 0,
            total_slashed: 0,
            total_paid: 0,
        }
    }
}

fn transfer(to: AccountId, amount: u128) {
    if amount > 0 {
        Promise::new(to).transfer(NearToken::from_yoctonear(amount));
    }
}

fn emit(event: &str, data_object: &str) {
    env::log_str(&format!(
        "EVENT_JSON:{{\"standard\":\"light-swarm\",\"version\":\"1.0.0\",\"event\":\"{event}\",\"data\":[{data_object}]}}"
    ));
}

fn sha256_hex(bytes: &[u8]) -> String {
    const HEX: &[u8; 16] = b"0123456789abcdef";
    let digest = env::sha256(bytes);
    let mut out = String::with_capacity(64);
    for byte in digest {
        out.push(HEX[(byte >> 4) as usize] as char);
        out.push(HEX[(byte & 0x0f) as usize] as char);
    }
    out
}

fn is_lower_hex64(text: &str) -> bool {
    text.len() == 64 && text.bytes().all(|byte| matches!(byte, b'0'..=b'9' | b'a'..=b'f'))
}

fn valid_salt(salt: &str) -> bool {
    (1..=64).contains(&salt.len()) && salt.bytes().all(|byte| byte.is_ascii_alphanumeric())
}

fn valid_grid(text: &str) -> bool {
    if text.is_empty() || text.len() > MAX_STRING || text.starts_with(';') || text.ends_with(';') {
        return false;
    }
    let rows: Vec<&str> = text.split(';').collect();
    if rows.is_empty() || rows.len() > MAX_SIDE {
        return false;
    }
    let width = rows[0].len();
    if width == 0 || width > MAX_SIDE {
        return false;
    }
    rows.iter().all(|row| row.len() == width && row.bytes().all(|byte| byte.is_ascii_digit()))
}

fn valid_demos(text: &str) -> bool {
    if text.is_empty() || text.len() > MAX_STRING {
        return false;
    }
    text.split('&').all(|part| {
        let mut pieces = part.split('|');
        match (pieces.next(), pieces.next(), pieces.next()) {
            (Some(left), Some(right), None) => valid_grid(left) && valid_grid(right),
            _ => false,
        }
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use near_sdk::test_utils::VMContextBuilder;
    use near_sdk::testing_env;

    const ANSWER: &str = "dc0be30dfb22566bbd5cdb3cc68c0617305d13377a3107320d87e3d86384c9a6";
    const COMMIT: &str = "32001f14d790be3047995d91e37743245991f57c932807fcbbb73ecff0bfd690";

    fn set_ctx(predecessor: &str, deposit: u128, block: u64) {
        let mut ctx = VMContextBuilder::new();
        ctx.predecessor_account_id(predecessor.parse().unwrap());
        ctx.signer_account_id(predecessor.parse().unwrap());
        ctx.current_account_id("market.test.near".parse().unwrap());
        ctx.attached_deposit(NearToken::from_yoctonear(deposit));
        ctx.account_balance(NearToken::from_near(50));
        ctx.block_height(block);
        testing_env!(ctx.build());
    }

    fn market() -> Market {
        set_ctx("owner.test.near", 0, 0);
        Market::new(U128(10_000))
    }

    fn post(market: &mut Market, answer: &str) -> u64 {
        set_ctx("req.test.near", 1000, 0);
        market.post_task("12;30|12;30".to_string(), "12;30".to_string(), answer.to_string(), U128(100), 8)
    }

    #[test]
    fn hash_vector_matches_python() {
        set_ctx("alice.test.near", 0, 0);
        assert_eq!(sha256_hex(b"12;30"), ANSWER);
        assert_eq!(sha256_hex(b"12;30|abc"), COMMIT);
    }

    #[test]
    fn solve_pays_and_updates_reputation() {
        let mut market = market();
        let task_id = post(&mut market, ANSWER);
        set_ctx("geo.test.near", 100, 0);
        market.register_agent();
        market.place_bid(task_id, U128(400), 8000);
        set_ctx("req.test.near", 0, 0);
        assert!(market.assign_best(task_id));
        set_ctx("geo.test.near", 0, 0);
        market.commit_solution(task_id, COMMIT.to_string());
        set_ctx("geo.test.near", 0, 1);
        let result = market.reveal_solution(task_id, "12;30".to_string(), "abc".to_string());
        assert!(result.correct);
        assert_eq!(result.solver_paid.0, 400);
        assert_eq!(result.requester_refund.0, 600);
        assert_eq!(market.get_agent("geo.test.near".parse().unwrap()).reputation, 1080);
        assert_eq!(market.get_task(task_id).status, "solved");
    }

    #[test]
    fn wrong_answer_is_slashed_then_reassigned() {
        let mut market = market();
        let task_id = post(&mut market, ANSWER);
        set_ctx("geo.test.near", 100, 0);
        market.place_bid(task_id, U128(300), 9000);
        set_ctx("obj.test.near", 100, 0);
        market.place_bid(task_id, U128(500), 8000);
        set_ctx("req.test.near", 0, 0);
        market.assign_best(task_id);
        assert_eq!(market.get_task(task_id).assignee.unwrap().as_str(), "geo.test.near");
        let bad = sha256_hex(b"11;11|abc");
        set_ctx("geo.test.near", 0, 0);
        market.commit_solution(task_id, bad);
        set_ctx("geo.test.near", 0, 1);
        let wrong = market.reveal_solution(task_id, "11;11".to_string(), "abc".to_string());
        assert!(!wrong.correct);
        assert_eq!(wrong.reason, "wrong_answer");
        assert_eq!(market.get_agent("geo.test.near".parse().unwrap()).reputation, 940);
        set_ctx("req.test.near", 0, 1);
        market.assign_best(task_id);
        assert_eq!(market.get_task(task_id).assignee.unwrap().as_str(), "obj.test.near");
        let good = sha256_hex(b"12;30|zz");
        set_ctx("obj.test.near", 0, 1);
        market.commit_solution(task_id, good);
        set_ctx("obj.test.near", 0, 2);
        let right = market.reveal_solution(task_id, "12;30".to_string(), "zz".to_string());
        assert!(right.correct);
        assert_eq!(right.solver_paid.0, 500);
        assert_eq!(market.get_task(task_id).slash_paid.0, 100);
    }

    #[test]
    fn subcontract_splits_the_price() {
        let mut market = market();
        let task_id = post(&mut market, ANSWER);
        set_ctx("obj.test.near", 0, 0);
        market.register_agent();
        set_ctx("geo.test.near", 100, 0);
        market.place_bid(task_id, U128(400), 8000);
        set_ctx("req.test.near", 0, 0);
        market.assign_best(task_id);
        set_ctx("geo.test.near", 0, 0);
        market.subcontract(task_id, "obj.test.near".parse().unwrap(), 2500);
        market.commit_solution(task_id, COMMIT.to_string());
        set_ctx("geo.test.near", 0, 1);
        let result = market.reveal_solution(task_id, "12;30".to_string(), "abc".to_string());
        assert_eq!(result.helper_paid.0, 100);
        assert_eq!(result.solver_paid.0, 300);
        assert_eq!(market.get_agent("obj.test.near".parse().unwrap()).reputation, 1020);
    }

    #[test]
    #[should_panic(expected = "reveal too early")]
    fn reveal_in_the_commit_block_is_rejected() {
        let mut market = market();
        let task_id = post(&mut market, ANSWER);
        set_ctx("geo.test.near", 100, 0);
        market.place_bid(task_id, U128(400), 8000);
        set_ctx("req.test.near", 0, 0);
        market.assign_best(task_id);
        set_ctx("geo.test.near", 0, 0);
        market.commit_solution(task_id, COMMIT.to_string());
        market.reveal_solution(task_id, "12;30".to_string(), "abc".to_string());
    }

    #[test]
    fn cancel_refunds_open_task() {
        let mut market = market();
        let task_id = post(&mut market, ANSWER);
        set_ctx("geo.test.near", 100, 0);
        market.place_bid(task_id, U128(400), 8000);
        set_ctx("req.test.near", 0, 0);
        market.cancel(task_id);
        let task = market.get_task(task_id);
        assert_eq!(task.status, "cancelled");
        assert_eq!(task.requester_refund.0, 1000);
        assert!(task.bids[0].refunded);
    }

    #[test]
    fn timeout_slashes_the_assignee() {
        let mut market = market();
        let task_id = post(&mut market, ANSWER);
        set_ctx("geo.test.near", 100, 0);
        market.place_bid(task_id, U128(400), 8000);
        set_ctx("req.test.near", 0, 0);
        market.assign_best(task_id);
        set_ctx("anyone.test.near", 0, 9);
        market.slash_timeout(task_id);
        assert_eq!(market.get_task(task_id).status, "open");
        assert_eq!(market.get_agent("geo.test.near".parse().unwrap()).reputation, 940);
    }

    #[test]
    #[should_panic(expected = "bad stake")]
    fn stake_above_the_cap_is_rejected() {
        let mut market = market();
        let task_id = post(&mut market, ANSWER);
        set_ctx("geo.test.near", 10_001, 0);
        market.place_bid(task_id, U128(400), 8000);
    }
}
