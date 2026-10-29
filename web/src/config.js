// The deployment's parameters: deployment.json at the root of the repository (the build resolves '@deployment' to it).
import deployment from '@deployment';

/** `deployment.rewardParams`, with the creator fee in it once the deployment has given it an address. */
export function rewardParamsOf({ rewardParams, creatorFee }) {
  const withFee = creatorFee && typeof creatorFee.address === 'string' && creatorFee.address && creatorFee.rateOfT > 0;
  return withFee ? { ...rewardParams, creatorFee: { address: creatorFee.address, rateOfT: creatorFee.rateOfT } } : { ...rewardParams };
}

export const config = { ...deployment, rewardParams: rewardParamsOf(deployment) };
