import React, { useEffect } from 'react';
import { useDispatch } from 'react-redux';
import styles from './Profile.module.scss';
import { type UserProfile } from './Profile.inerface';

// Temporary mock data mapping to your HTML layout
const mockUser: UserProfile = {
  firstName: 'Super User',
  lastName: '-',
  userName: 'superuser@onixnet.com',
  email: 'superuser@onixnet.com',
  role: 'ADMINISTRATOR',
  assignedWorkspaces: 'PELICAN',
  lastLoginTime: '2026-06-12 11:47:03',
  organization: '-',
  team: '-',
  location: '-',
  isLocal: true,
};

const Profile: React.FC = () => {
  const dispatch = useDispatch();
  
  // Example of how you would connect this to your Redux state:
  // const { data, isLoading } = useSelector((state: any) => state.profile);
  const data = mockUser; // Using mock data for UI representation

  useEffect(() => {
    // dispatch({ type: 'FETCH_PROFILE_REQUEST' });
  }, [dispatch]);

  if (!data) return <div>Loading...</div>;

  return (
    <div className="bg-background text-on-surface min-h-screen">
      <main className="max-w-[960px] mx-auto px-4 md:px-0 py-8 flex flex-col gap-6">
        
        {/* Card A (Header) */}
        <section className={`bg-surface-container-lowest rounded-lg p-6 ${styles.cardShadow}`}>
          <h1 className="text-xl font-bold text-primary font-headline-md text-headline-md">
            Profile
          </h1>
        </section>

        {/* Card B (User Details) */}
        <section className={`bg-surface-container-lowest rounded-lg p-6 ${styles.cardShadow}`}>
          <div className="flex items-center gap-3 mb-8">
            <h2 className="text-lg font-semibold text-on-surface font-headline-sm text-headline-sm">
              User Details
            </h2>
            {data.isLocal && (
              <span className="px-3 py-1 bg-primary-fixed text-on-primary-fixed-variant text-[12px] font-medium rounded-full uppercase tracking-wider">
                LOCAL
              </span>
            )}
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-x-12 gap-y-6">
            
            <div className="flex flex-col gap-2">
              <label className="text-[12px] font-medium text-outline uppercase tracking-tight">First Name</label>
              <p className="text-[14px] font-semibold text-on-surface">{data.firstName}</p>
            </div>

            <div className="flex flex-col gap-2">
              <label className="text-[12px] font-medium text-outline uppercase tracking-tight">Last Name</label>
              <p className="text-[14px] font-semibold text-on-surface">{data.lastName}</p>
            </div>

            <div className="flex flex-col gap-2">
              <label className="text-[12px] font-medium text-outline uppercase tracking-tight">User Name</label>
              <p className="text-[14px] font-semibold text-on-surface">{data.userName}</p>
            </div>

            <div className="flex flex-col gap-2">
              <label className="text-[12px] font-medium text-outline uppercase tracking-tight">Email</label>
              <div className="flex items-center gap-2">
                <span className="material-symbols-outlined text-[18px] text-primary">mail</span>
                <p className="text-[14px] font-semibold text-on-surface">{data.email}</p>
              </div>
            </div>

            <div className="flex flex-col gap-2">
              <label className="text-[12px] font-medium text-outline uppercase tracking-tight">Role</label>
              <div>
                <span className="px-3 py-1 bg-secondary-container text-on-secondary-fixed-variant text-[12px] font-bold rounded-full">
                  {data.role}
                </span>
              </div>
            </div>

            <div className="flex flex-col gap-2">
              <label className="text-[12px] font-medium text-outline uppercase tracking-tight">Assigned Workspaces</label>
              <div>
                <span className="px-3 py-1 bg-primary-fixed text-on-primary-fixed-variant text-[12px] font-bold rounded-full">
                  {data.assignedWorkspaces}
                </span>
              </div>
            </div>

            <div className="flex flex-col gap-2">
              <label className="text-[12px] font-medium text-outline uppercase tracking-tight">Last Login Time</label>
              <div className="flex items-center gap-2">
                <span className="material-symbols-outlined text-[18px] text-outline">history</span>
                <p className="text-[14px] font-semibold text-on-surface">{data.lastLoginTime}</p>
              </div>
            </div>

            <div className="flex flex-col gap-2">
              <label className="text-[12px] font-medium text-outline uppercase tracking-tight">Organization</label>
              <p className="text-[14px] font-semibold text-on-surface">{data.organization}</p>
            </div>

            <div className="flex flex-col gap-2">
              <label className="text-[12px] font-medium text-outline uppercase tracking-tight">Team</label>
              <p className="text-[14px] font-semibold text-on-surface">{data.team}</p>
            </div>

            <div className="flex flex-col gap-2">
              <label className="text-[12px] font-medium text-outline uppercase tracking-tight">Location</label>
              <div className="flex items-center gap-2">
                <span className="material-symbols-outlined text-[18px] text-outline">location_on</span>
                <p className="text-[14px] font-semibold text-on-surface">{data.location}</p>
              </div>
            </div>

          </div>
        </section>

        {/* Card C (Password) */}
        <section className={`bg-surface-container-lowest rounded-lg p-6 ${styles.cardShadow}`}>
          <h2 className="text-lg font-semibold text-on-surface font-headline-sm text-headline-sm mb-6">
            Password
          </h2>
          <div>
            <button className={`${styles.btnPrimaryOutline} px-6 py-2.5 rounded font-medium text-sm inline-flex items-center gap-2`}>
              <span className="material-symbols-outlined text-[18px]">lock_reset</span>
              Reset Password
            </button>
          </div>
        </section>

      </main>

      <footer className="max-w-[960px] mx-auto px-4 py-12 text-center text-outline text-[12px]">
        © 2026 Pelican Systems • Administrative Profile Management Interface
      </footer>
    </div>
  );
};

export default Profile;