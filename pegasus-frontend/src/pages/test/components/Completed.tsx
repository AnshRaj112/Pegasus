import { Skeleton } from 'antd';
import { useAppSelector } from '~/redux/store';
import styles from '../Test.module.scss';

const CompletedView = () => {
  const { data, isFetching } = useAppSelector((state) => state.test.completedTests);

  if (isFetching) {
    return <div className="p-4"><Skeleton active paragraph={{ rows: 5 }} /></div>;
  }

  if (!data || data.length === 0) {
    return <div className="p-4 text-center text-muted">No completed tests found.</div>;
  }

  return (
    <div>
      {data.map((test) => (
        <div key={test.id} className={`d-flex justify-content-between align-items-center ${styles.listRow}`}>
          <div className="d-flex align-items-center col-5">
            <div className={`me-3 text-muted small ${styles.endedBlock}`}>
              <div>Ended</div>
              <div>{test.endedDate}</div>
              <div>{test.endedTime}</div>
            </div>
            <span className="me-2 text-secondary">⊟</span>
            <div>
              <div className="fw-bold">{test.title}</div>
              <div className="text-muted small">{test.subtitle}</div>
            </div>
          </div>
          
          <div className="col-3 text-muted small d-flex align-items-center">
            <span className="me-2">↺</span> {test.schedule}
          </div>
          
          <div className="col-4 d-flex justify-content-end align-items-center gap-2">
            {test.status === 'Incoherent' ? (
              <span className={`${styles.statusBadge} ${styles['statusBadge--incoherent']}`}>Incoherent <span className={styles['typeIcon--red']}>{test.type}</span></span>
            ) : (
              <span className={styles.statusBadge}>{test.status} {test.type}</span>
            )}
            
            {test.result && (
              <span className={`${styles.statusBadge} ${test.result === 'Pass' ? styles['statusBadge--pass'] : styles['statusBadge--fail']}`}>
                {test.duration} {test.result} <span className={test.result === 'Fail' ? styles['typeIcon--red'] : styles.typeIcon}>{test.type}</span>
              </span>
            )}
            
            <button className={`d-flex align-items-center ${styles.snippetBtn}`}>
              Snippet <span className="ms-1">📄</span>
            </button>
          </div>
        </div>
      ))}
    </div>
  );
};

export default CompletedView;